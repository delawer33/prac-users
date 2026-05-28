import asyncio
import json
import logging
from uuid import UUID

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from aiokafka.structs import ConsumerRecord, TopicPartition
from sqlalchemy.exc import SQLAlchemyError

from src.config import Settings
from src.db import SessionFactory
from src.exceptions import PermanentEventError, TransientRetriesExhausted
from src.repositories.processed_messages import ProcessedMessagesRepository
from src.workers.db_error_classifier import error_reason, is_transient, pgcode
from src.workers.event_handlers import OrderFeedbackCreatedEventHandler

logger = logging.getLogger(__name__)
settings = Settings()


class RetryPolicy:
    def __init__(
        self, *, initial_seconds: float, cap_seconds: float, max_attempts: int
    ) -> None:
        self._initial_seconds = initial_seconds
        self._cap_seconds = cap_seconds
        self._seconds = initial_seconds
        self.max_attempts = max_attempts

    async def wait_before_retry(self) -> None:
        await asyncio.sleep(self._seconds)
        self._seconds = min(self._seconds * 2, self._cap_seconds)

    def reset(self) -> None:
        self._seconds = self._initial_seconds

    @property
    def next_backoff_seconds(self) -> float:
        return self._seconds


class KafkaIO:
    def __init__(
        self,
        consumer: AIOKafkaConsumer,
        dlq_producer: AIOKafkaProducer,
        *,
        dlq_topic: str,
    ) -> None:
        self._consumer = consumer
        self._dlq_producer = dlq_producer
        self.dlq_topic = dlq_topic

    @staticmethod
    def message_ref(msg: ConsumerRecord, *, event_id: str | None = None) -> str:
        return (
            f"topic={msg.topic} partition={msg.partition} offset={msg.offset} "
            f"event_id={event_id or '-'}"
        )

    async def commit_message(self, msg: ConsumerRecord) -> None:
        tp = TopicPartition(msg.topic, msg.partition)
        await self._consumer.commit({tp: msg.offset + 1})

    async def publish_to_dlq(self, raw_value: bytes) -> None:
        await self._dlq_producer.send_and_wait(self.dlq_topic, value=raw_value)


class OrderEventsConsumer:
    def __init__(self, kafka: KafkaIO, retry: RetryPolicy) -> None:
        self._kafka = kafka
        self._retry = retry

    async def process_message(self, msg: ConsumerRecord) -> None:
        # Пробуем обработать сообщение self._max_attempts раз
        # Если все попытки исчерпаны, значит бд или кафка лежит, выходим из воркера
        for attempt in range(1, self._retry.max_attempts + 1):
            if await self._attempt(msg, attempt=attempt):
                self._retry.reset()
                return
            if attempt == self._retry.max_attempts:
                ref = self._kafka.message_ref(msg)
                logger.critical(
                    "transient retries exhausted %s attempts=%s — not committing, stopping consumer",
                    ref,
                    self._retry.max_attempts,
                )
                raise TransientRetriesExhausted(
                    message_ref=ref,
                    attempts=self._retry.max_attempts,
                    detail="db or dlq publish still failing",
                )
            logger.warning(
                "retry scheduled %s attempt=%s/%s next_backoff_seconds=%s",
                self._kafka.message_ref(msg),
                attempt,
                self._retry.max_attempts,
                self._retry.next_backoff_seconds,
            )
            await self._retry.wait_before_retry()

    async def _attempt(self, msg: ConsumerRecord, *, attempt: int) -> bool:
        """Сделать попытку обработки, возвращает False если нужно заретраить, True если нет"""
        try:
            payload = json.loads(msg.value)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error(
                "failed to decode message %s: %s",
                self._kafka.message_ref(msg),
                exc,
            )
            return await self._discard(msg, reason="invalid_json", attempt=attempt)

        try:
            event_id = UUID(payload["event_id"])
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(
                "missing or invalid event_id %s: %s",
                self._kafka.message_ref(msg),
                exc,
            )
            return await self._discard(
                msg, reason=f"missing_event_id: {exc}", attempt=attempt
            )

        ref = self._kafka.message_ref(msg, event_id=str(event_id))
        try:
            async with SessionFactory() as session:
                is_new = await ProcessedMessagesRepository(session).try_mark_processed(
                    event_id=event_id, topic=msg.topic
                )
                if is_new:
                    await OrderFeedbackCreatedEventHandler(session).handle(payload)
                await session.commit()
        except PermanentEventError as exc:
            logger.error("permanent event error %s reason=%s", ref, exc.reason)
            return await self._discard(
                msg, reason=exc.reason, event_id=str(event_id), attempt=attempt
            )
        except SQLAlchemyError as exc:
            if is_transient(exc):
                logger.exception(
                    "transient db error %s attempt=%s/%s pgcode=%s — not committing",
                    ref,
                    attempt,
                    self._retry.max_attempts,
                    pgcode(exc) or "-",
                )
                return False
            logger.error("permanent db error %s reason=%s", ref, exc)
            return await self._discard(
                msg, reason=error_reason(exc), event_id=str(event_id), attempt=attempt
            )
        except Exception:
            # Вероятно ошибка в коде, выходим из воркера
            logger.exception(
                "unexpected error %s — not committing, failing consumer", ref
            )
            raise

        if not is_new:
            logger.info(
                "duplicate event_id=%s topic=%s — skipping", event_id, msg.topic
            )
        return await self._commit_offset(
            msg, attempt=attempt, ref=ref, context="after_success"
        )

    async def _commit_offset(
        self,
        msg: ConsumerRecord,
        *,
        attempt: int,
        ref: str,
        context: str,
    ) -> bool:
        try:
            await self._kafka.commit_message(msg)
            return True
        except KafkaError:
            logger.exception(
                "offset commit failed %s attempt=%s/%s context=%s",
                ref,
                attempt,
                self._retry.max_attempts,
                context,
            )
            return False

    async def _discard(
        self,
        msg: ConsumerRecord,
        *,
        reason: str,
        attempt: int,
        event_id: str | None = None,
    ) -> bool:
        """Отправить в DLQ и закоммитить. Возвращает False если нужно заретраить, True если нет"""
        ref = self._kafka.message_ref(msg, event_id=event_id)
        try:
            await self._kafka.publish_to_dlq(msg.value)
            logger.warning(
                "message sent to DLQ %s reason=%s dlq_topic=%s",
                ref,
                reason,
                self._kafka.dlq_topic,
            )
        except KafkaError:
            logger.exception(
                "DLQ publish failed %s attempt=%s/%s reason=%s — not committing",
                ref,
                attempt,
                self._retry.max_attempts,
                reason,
            )
            return False

        return await self._commit_offset(
            msg,
            attempt=attempt,
            ref=ref,
            context="after_dlq",
        )


async def run_consumer() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    kafka_consumer = AIOKafkaConsumer(
        settings.kafka_order_feedback_created_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    dlq_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        acks="all",
    )

    await kafka_consumer.start()
    await dlq_producer.start()
    logger.info("order feedback events consumer started")

    kafka_io = KafkaIO(
        kafka_consumer,
        dlq_producer,
        dlq_topic=settings.kafka_order_feedback_created_dlq_topic,
    )
    app = OrderEventsConsumer(
        kafka_io,
        RetryPolicy(
            initial_seconds=settings.consumer_retry_initial_seconds,
            cap_seconds=settings.consumer_retry_cap_seconds,
            max_attempts=settings.consumer_retry_max_attempts,
        ),
    )

    try:
        async for msg in kafka_consumer:
            await app.process_message(msg)
    finally:
        await kafka_consumer.stop()
        await dlq_producer.stop()
        logger.info("order feedback events consumer stopped")


if __name__ == "__main__":
    asyncio.run(run_consumer())
