from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokafka.errors import KafkaConnectionError
from aiokafka.structs import ConsumerRecord
from sqlalchemy.exc import IntegrityError, OperationalError

from src.exceptions import TransientRetriesExhausted
from src.workers.db_error_classifier import is_transient, pgcode
from src.workers.order_events_consumer import (
    KafkaIO,
    OrderEventsConsumer,
    RetryPolicy,
)


def _msg() -> ConsumerRecord:
    return ConsumerRecord(
        topic="orders.order-feedback-created",
        partition=0,
        offset=42,
        timestamp=0,
        timestamp_type=0,
        key=None,
        value=b'{"event_id":"00000000-0000-0000-0000-000000000001","data":{}}',
        checksum=None,
        serialized_key_size=-1,
        serialized_value_size=-1,
        headers=(),
    )


def _operational_error(pg_code: str | None) -> OperationalError:
    # Use a plain exception for "no sqlstate" — MagicMock auto-creates truthy attributes.
    if pg_code is None:
        orig: Exception = Exception("connection lost")
    else:
        orig = MagicMock()
        orig.sqlstate = pg_code
        orig.pgcode = None
    return OperationalError("stmt", {}, orig)


def _retry(max_attempts: int = 5) -> RetryPolicy:
    return RetryPolicy(initial_seconds=0.0, cap_seconds=0.0, max_attempts=max_attempts)


def _patch_new_event():
    """Patch try_mark_processed to return True (new event), so handler is invoked."""
    return patch(
        "src.workers.order_events_consumer.ProcessedMessagesRepository.try_mark_processed",
        new_callable=AsyncMock,
        return_value=True,
    )


@pytest.mark.parametrize(
    ("pg_code", "expected"),
    [
        ("40P01", True),
        ("08006", True),
        (None, True),
        ("42P01", False),
        ("23505", False),
    ],
)
def test_is_transient_db_error_operational(pg_code: str | None, expected: bool) -> None:
    assert is_transient(_operational_error(pg_code)) is expected


def test_is_transient_db_error_integrity_is_permanent() -> None:
    assert is_transient(IntegrityError("stmt", {}, Exception())) is False


def test_pgcode_from_sqlstate() -> None:
    assert pgcode(_operational_error("40P01")) == "40P01"


@pytest.mark.asyncio
async def test_unexpected_error_propagates_without_dlq_or_commit() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    consumer = OrderEventsConsumer(kafka, _retry())

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
            side_effect=RuntimeError("bug"),
        ):
            with pytest.raises(RuntimeError, match="bug"):
                await consumer._attempt(_msg(), attempt=1)

    kafka.publish_to_dlq.assert_not_called()
    kafka.commit_message.assert_not_called()


@pytest.mark.asyncio
async def test_transient_db_error_retries_then_crashes() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    consumer = OrderEventsConsumer(kafka, _retry(max_attempts=3))

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
            side_effect=_operational_error("08006"),
        ):
            with pytest.raises(TransientRetriesExhausted):
                await consumer.process_message(_msg())

    assert kafka.commit_message.await_count == 0
    assert kafka.publish_to_dlq.await_count == 0


@pytest.mark.asyncio
async def test_permanent_db_error_discards_to_dlq() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    kafka.dlq_topic = "orders.order-feedback-created.dlq"
    kafka.publish_to_dlq = AsyncMock()
    kafka.commit_message = AsyncMock()
    consumer = OrderEventsConsumer(kafka, _retry(max_attempts=3))

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
            side_effect=IntegrityError("stmt", {}, Exception()),
        ):
            await consumer.process_message(_msg())

    kafka.publish_to_dlq.assert_awaited_once()
    kafka.commit_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_dlq_publish_failure_retries_then_crashes() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    kafka.publish_to_dlq = AsyncMock(side_effect=KafkaConnectionError("kafka down"))
    consumer = OrderEventsConsumer(kafka, _retry(max_attempts=2))

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
            side_effect=IntegrityError("stmt", {}, Exception()),
        ):
            with pytest.raises(TransientRetriesExhausted):
                await consumer.process_message(_msg())

    assert kafka.publish_to_dlq.await_count == 2
    kafka.commit_message.assert_not_called()


@pytest.mark.asyncio
async def test_offset_commit_failure_retries_then_succeeds() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    kafka.commit_message = AsyncMock(
        side_effect=[KafkaConnectionError("coordinator down"), None]
    )
    consumer = OrderEventsConsumer(kafka, _retry(max_attempts=3))

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
        ):
            await consumer.process_message(_msg())

    assert kafka.commit_message.await_count == 2


@pytest.mark.asyncio
async def test_offset_commit_failure_after_dlq_retries() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=-"
    kafka.dlq_topic = "orders.order-feedback-created.dlq"
    kafka.publish_to_dlq = AsyncMock()
    kafka.commit_message = AsyncMock(
        side_effect=[KafkaConnectionError("coordinator down"), None]
    )
    consumer = OrderEventsConsumer(kafka, _retry(max_attempts=3))

    with _patch_new_event():
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
            side_effect=IntegrityError("stmt", {}, Exception()),
        ):
            await consumer.process_message(_msg())

    assert kafka.publish_to_dlq.await_count == 2
    assert kafka.commit_message.await_count == 2


@pytest.mark.asyncio
async def test_duplicate_event_skips_handler_and_commits_offset() -> None:
    kafka = MagicMock(spec=KafkaIO)
    kafka.message_ref.return_value = "topic=t partition=0 offset=42 event_id=00000000-0000-0000-0000-000000000001"
    kafka.commit_message = AsyncMock()
    consumer = OrderEventsConsumer(kafka, _retry())

    with patch(
        "src.workers.order_events_consumer.ProcessedMessagesRepository.try_mark_processed",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with patch(
            "src.workers.order_events_consumer.OrderFeedbackCreatedEventHandler.handle",
            new_callable=AsyncMock,
        ) as mock_handle:
            await consumer.process_message(_msg())

    mock_handle.assert_not_called()
    kafka.commit_message.assert_awaited_once()
