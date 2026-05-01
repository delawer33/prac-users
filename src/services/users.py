import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import (
    UserNotFoundError,
)
from src.repositories import users as users_repo
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse

logger = logging.getLogger(__name__)


async def get_user(session: AsyncSession, user_id: UUID) -> UserRead:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return UserRead.model_validate(user)


async def create_user(session: AsyncSession, data: UserCreate) -> UserRead:
    user = await users_repo.create_user(
        session,
        username=data.username,
        email=str(data.email),
        first_name=data.first_name,
        last_name=data.last_name,
    )
    logger.info("user created user_id=%s", user.id)
    return UserRead.model_validate(user)


async def resolve_user(session: AsyncSession, data: UserResolveRequest) -> UserResolveResponse:
    user, created_by_request = await users_repo.resolve_user_for_request(
        session=session,
        external_request_id=data.external_request_id,
        email=str(data.email),
    )
    logger.info(
        "user resolved user_id=%s external_request_id=%s created=%s",
        user.id,
        data.external_request_id,
        created_by_request,
    )
    return UserResolveResponse(
        user=UserRead.model_validate(user),
        created=created_by_request,
    )


async def cancel_user_for_order_saga(session: AsyncSession, user_id: UUID) -> None:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)

    if await users_repo.was_user_created_by_request(session, user_id):
        await users_repo.deactivate_user(session, user)

    logger.info("user saga cancellation processed user_id=%s", user_id)
