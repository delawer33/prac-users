import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy.exc import SQLAlchemyError

from src.config import Settings
from src.db import SessionFactory
from src.exceptions import PermanentEventError
from src.workers.event_handlers import OrderCreatedEventHandler

logger = logging.getLogger(__name__)
settings = Settings()


async def _send_to_dlq(producer: AIOKafkaProducer, raw_value: bytes) -> None:
    try:
        await producer.send(settings.kafka_order_created_dlq_topic, value=raw_value)
        await producer.flush()
        logger.warning("message sent to DLQ")
    except KafkaError:
        logger.exception("failed to send message to DLQ")


async def run_consumer() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    consumer = AIOKafkaConsumer(
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

    await consumer.start()
    await dlq_producer.start()
    logger.info("order events consumer started")

    try:
        async for msg in consumer:
            try:
                payload = json.loads(msg.value)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.error("failed to decode message offset=%s: %s", msg.offset, exc)
                await _send_to_dlq(dlq_producer, msg.value)
                await consumer.commit()
                continue

            try:
                async with SessionFactory() as session:
                    handler = OrderCreatedEventHandler(session)
                    await handler.handle(payload)
                await consumer.commit()
            except PermanentEventError as exc:
                logger.error("permanent event error offset=%s reason=%s", msg.offset, exc.reason)
                await _send_to_dlq(dlq_producer, msg.value)
                await consumer.commit()
            except SQLAlchemyError:
                logger.exception(
                    "transient db error offset=%s — not committing, will retry",
                    msg.offset,
                )
            except Exception:
                logger.exception("unexpected error offset=%s — not committing, will retry", msg.offset)
    finally:
        await consumer.stop()
        await dlq_producer.stop()
        logger.info("order events consumer stopped")


if __name__ == "__main__":
    asyncio.run(run_consumer())
