from uuid import uuid4

import pytest

from src.exceptions import PermanentEventError
from src.repositories.users import UsersRepository
from src.workers.event_handlers import OrderCreatedEventHandler
from tests.conftest import create_user

ORDER_ID = uuid4()
USER_ID = uuid4()

_VALID_PAYLOAD = {
    "event_id": str(ORDER_ID),
    "event_type": "OrderCreated",
    "occurred_at": "2024-06-01T12:00:00+00:00",
    "data": {
        "order_id": str(ORDER_ID),
        "user_id": str(USER_ID),
        "total_amount": 24.98,
        "created_at": "2024-06-01T12:00:00+00:00",
    },
}


# happy path

async def test_handle_order_created_updates_user_stats(db_session):
    user = await create_user(db_session, user_id=USER_ID)
    assert user.orders_count == 0

    handler = OrderCreatedEventHandler(db_session)
    await handler.handle(_VALID_PAYLOAD)

    updated = await UsersRepository(db_session).get_user(USER_ID)
    assert updated.orders_count == 1
    assert abs(float(updated.total_spent) - 24.98) < 0.001
    assert updated.last_ordered_at is not None


# Дедупликация

async def test_handle_duplicate_event_does_not_update_stats(db_session):
    await create_user(db_session, user_id=USER_ID)

    handler = OrderCreatedEventHandler(db_session)
    await handler.handle(_VALID_PAYLOAD)
    await handler.handle(_VALID_PAYLOAD)

    updated = await UsersRepository(db_session).get_user(USER_ID)
    assert updated.orders_count == 1


# Правильная обработка плохих данных

async def test_handle_bad_payload_raises_permanent_event_error(db_session):
    await create_user(db_session, user_id=USER_ID)

    bad_payload = {"event_id": str(ORDER_ID), "event_type": "OrderCreated"}  # не хватает столбцов

    handler = OrderCreatedEventHandler(db_session)
    with pytest.raises(PermanentEventError):
        await handler.handle(bad_payload)

    updated = await UsersRepository(db_session).get_user(USER_ID)
    assert updated.orders_count == 0
