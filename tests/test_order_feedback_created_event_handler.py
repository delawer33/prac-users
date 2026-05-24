from uuid import uuid4

import pytest

from src.exceptions import PermanentEventError
from src.repositories.users import UsersRepository
from src.workers.event_handlers import OrderFeedbackCreatedEventHandler
from tests.conftest import create_user

FEEDBACK_ID = uuid4()
USER_ID = uuid4()

_VALID_PAYLOAD = {
    "event_id": str(FEEDBACK_ID),
    "event_type": "OrderFeedbackCreated",
    "occurred_at": "2024-06-01T12:00:00+00:00",
    "data": {
        "feedback_id": str(FEEDBACK_ID),
        "order_id": str(uuid4()),
        "user_id": str(USER_ID),
    },
}


async def test_handle_order_feedback_created_increments_feedbacks_count(db_session):
    user = await create_user(db_session, user_id=USER_ID)
    assert user.feedbacks_count == 0

    handler = OrderFeedbackCreatedEventHandler(db_session)
    await handler.handle(_VALID_PAYLOAD)

    updated = await UsersRepository(db_session).get_user(USER_ID)
    assert updated is not None
    assert updated.feedbacks_count == 1



async def test_handle_missing_user_raises_permanent_event_error(db_session):
    handler = OrderFeedbackCreatedEventHandler(db_session)
    with pytest.raises(PermanentEventError, match="user not found"):
        await handler.handle(_VALID_PAYLOAD)


async def test_handle_bad_payload_raises_permanent_event_error(db_session):
    await create_user(db_session, user_id=USER_ID)

    bad_payload = {"event_id": str(FEEDBACK_ID), "event_type": "OrderFeedbackCreated"}

    handler = OrderFeedbackCreatedEventHandler(db_session)
    with pytest.raises(PermanentEventError):
        await handler.handle(bad_payload)

    updated = await UsersRepository(db_session).get_user(USER_ID)
    assert updated is not None
    assert updated.feedbacks_count == 0
