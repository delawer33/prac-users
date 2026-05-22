import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from aiokafka.structs import ConsumerRecord, TopicPartition
from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError as SQLTimeoutError,
)

from src.config import Settings
from src.db import SessionFactory
from src.exceptions import PermanentEventError
from src.workers.event_handlers import OrderCreatedEventHandler

logger = logging.getLogger(__name__)
settings = Settings()


class RetryPolicy:
    def __init__(self, *, initial_seconds: float = 1.0, cap_seconds: float = 30.0) -> None:
        self._initial_seconds = initial_seconds
        self._cap_seconds = cap_seconds
        self._seconds = initial_seconds

    async def wait_before_retry(self) -> None:
        await asyncio.sleep(self._seconds)
        self._seconds = min(self._seconds * 2, self._cap_seconds)

    def reset(self) -> None:
        self._seconds = self._initial_seconds


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
        await self._dlq_producer.send(self.dlq_topic, value=raw_value)
        await self._dlq_producer.flush()


class OrderEventsConsumer:
    def __init__(self, kafka: KafkaIO, retry: RetryPolicy) -> None:
        self._kafka = kafka
        self._retry = retry

    async def process_message(self, msg: ConsumerRecord) -> None:
        while True:
            if await self._attempt(msg):
                self._retry.reset()
                return
            await self._retry.wait_before_retry()

    async def _attempt(self, msg: ConsumerRecord) -> bool:
        """Сделать попытку обработки, возвращает False если нужно заретраить, True если нет"""
        try:
            payload = json.loads(msg.value)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error(
                "failed to decode message %s: %s",
                self._kafka.message_ref(msg),
                exc,
            )
            return await self._discard(msg, reason="invalid_json")

        try:
            async with SessionFactory() as session:
                await OrderCreatedEventHandler(session).handle(payload)
                await session.commit()
        except PermanentEventError as exc:
            logger.error(
                "permanent event error %s reason=%s",
                self._kafka.message_ref(msg, event_id=_event_id(payload)),
                exc.reason,
            )
            return await self._discard(
                msg,
                reason=exc.reason,
                event_id=_event_id(payload),
            )
        except SQLAlchemyError as exc:
            ref = self._kafka.message_ref(msg, event_id=_event_id(payload))
            if _is_transient_db_error(exc):
                logger.exception(
                    "transient db error %s — not committing, will retry",
                    ref,
                )
                return False
            logger.error("permanent db error %s reason=%s", ref, exc)
            return await self._discard(
                msg,
                reason=_db_error_reason(exc),
                event_id=_event_id(payload),
            )
        except Exception as exc:
            logger.exception(
                "unexpected error %s type=%s — sending to DLQ",
                self._kafka.message_ref(msg, event_id=_event_id(payload)),
                type(exc).__name__,
            )
            return await self._discard(
                msg,
                reason=f"unexpected_{type(exc).__name__}: {exc}",
                event_id=_event_id(payload),
            )

        await self._kafka.commit_message(msg)
        return True

    async def _discard(
        self,
        msg: ConsumerRecord,
        *,
        reason: str,
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
            logger.exception("DLQ failed %s reason=%s", ref, reason)
            return False

        await self._kafka.commit_message(msg)
        return True


def _event_id(payload: dict) -> str | None:
    value = payload.get("event_id")
    return str(value) if value is not None else None


def _is_transient_db_error(exc: SQLAlchemyError) -> bool:
    return isinstance(exc, (OperationalError, InterfaceError, SQLTimeoutError))


def _db_error_reason(exc: SQLAlchemyError) -> str:
    return f"db_{type(exc).__name__}: {exc}"


async def run_consumer() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    kafka_consumer = AIOKafkaConsumer(
        settings.kafka_order_created_topic,
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
    logger.info("order events consumer started")

    kafka_io = KafkaIO(
        kafka_consumer,
        dlq_producer,
        dlq_topic=settings.kafka_order_created_dlq_topic,
    )
    app = OrderEventsConsumer(kafka_io, RetryPolicy())

    try:
        async for msg in kafka_consumer:
            await app.process_message(msg)
    finally:
        await kafka_consumer.stop()
        await dlq_producer.stop()
        logger.info("order events consumer stopped")


if __name__ == "__main__":
    asyncio.run(run_consumer())
