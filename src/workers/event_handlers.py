import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import PermanentEventError
from src.repositories.processed_messages import ProcessedMessagesRepository
from src.repositories.users import UsersRepository

logger = logging.getLogger(__name__)

TOPIC_ORDER_CREATED = "orders.order-created"


class OrderCreatedEventHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._users_repo = UsersRepository(session)
        self._processed_repo = ProcessedMessagesRepository(session)

    async def handle(self, payload: dict) -> None:
        try:
            data = payload["data"]
            event_id = UUID(payload["event_id"])
            user_id = UUID(data["user_id"])
            total_amount = float(data["total_amount"])
            occurred_at = datetime.fromisoformat(payload["occurred_at"])
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, TypeError) as exc:
            # Сообщение невалидно, сразу выкидываем PermanentEventError и далее оно идет в DLQ
            raise PermanentEventError(f"malformed OrderCreated payload: {exc}") from exc

        if not await self._processed_repo.try_mark_processed(
            event_id=event_id,
            topic=TOPIC_ORDER_CREATED,
        ):
            logger.info("OrderCreated already processed event_id=%s", event_id)
            return

        if not await self._users_repo.update_user_stats(
            user_id,
            amount=total_amount,
            ordered_at=occurred_at,
        ):
            raise PermanentEventError(f"user not found: {user_id}")

        logger.info("OrderCreated processed event_id=%s user_id=%s", event_id, user_id)
