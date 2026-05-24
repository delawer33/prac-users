import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import PermanentEventError
from src.repositories.users import UsersRepository

logger = logging.getLogger(__name__)


class OrderFeedbackCreatedEventHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._users_repo = UsersRepository(session)

    async def handle(self, payload: dict) -> None:
        try:
            user_id = UUID(payload["data"]["user_id"])
        except (KeyError, ValueError, TypeError) as exc:
            raise PermanentEventError(
                f"malformed OrderFeedbackCreated payload: {exc}"
            ) from exc

        if not await self._users_repo.increment_feedbacks_count(user_id):
            raise PermanentEventError(f"user not found: {user_id}")

        logger.info("OrderFeedbackCreated processed user_id=%s", user_id)
