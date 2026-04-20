import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import UserEmailAlreadyExistsError, UserNotFoundError
from src.repositories import users as users_repo
from src.schemas.users import UserCreate, UserRead

logger = logging.getLogger(__name__)


async def get_user(session: AsyncSession, user_id: UUID) -> UserRead:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return UserRead.model_validate(user)


async def create_user(session: AsyncSession, data: UserCreate) -> UserRead:
    try:
        user = await users_repo.create_user(session, data)
    except IntegrityError as exc:
        raise UserEmailAlreadyExistsError(str(data.email)) from exc
    logger.info("user created user_id=%s", user.id)
    return UserRead.model_validate(user)
