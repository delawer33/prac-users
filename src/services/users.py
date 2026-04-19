import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import users as users_repo
from src.schemas.users import UserCreate, UserRead

logger = logging.getLogger(__name__)


async def get_user(session: AsyncSession, user_id: UUID) -> UserRead:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


async def create_user(session: AsyncSession, data: UserCreate) -> UserRead:
    user = await users_repo.create_user(session, data)
    logger.info("user created user_id=%s username=%r", user.id, user.username)
    return UserRead.model_validate(user)
