from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import InvariantViolationError
from src.models.user_resolve_requests import UserResolveRequestModel
from src.models.users import UserModel


async def get_user(session: AsyncSession, user_id: UUID) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
) -> UserModel:
    user = UserModel(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


async def create_resolved_user(session: AsyncSession, email: str) -> UserModel:
    user = UserModel(
        username=None,
        email=email,
        first_name=None,
        last_name=None,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def activate_user(session: AsyncSession, user: UserModel) -> UserModel:
    user.is_active = True
    await session.flush()
    await session.refresh(user)
    return user


async def deactivate_user(session: AsyncSession, user: UserModel) -> UserModel:
    user.is_active = False
    await session.flush()
    await session.refresh(user)
    return user


async def was_user_created_by_request(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        select(UserResolveRequestModel.id).where(
            UserResolveRequestModel.user_id == user_id,
            UserResolveRequestModel.created_by_request.is_(True),
        )
    )
    return result.first() is not None


async def get_resolve_request(
    session: AsyncSession,
    external_request_id: str,
) -> UserResolveRequestModel | None:
    result = await session.execute(
        select(UserResolveRequestModel).where(
            UserResolveRequestModel.external_request_id == external_request_id
        )
    )
    return result.scalar_one_or_none()


async def create_resolve_request(
    session: AsyncSession,
    *,
    external_request_id: str,
    user_id: UUID,
    created_by_request: bool,
) -> UserResolveRequestModel:
    stmt = (
        pg_insert(UserResolveRequestModel)
        .values(
            external_request_id=external_request_id,
            user_id=user_id,
            created_by_request=created_by_request,
        )
        .on_conflict_do_nothing(index_elements=["external_request_id"])
    )
    await session.execute(stmt)

    resolve_request = await get_resolve_request(session, external_request_id)
    if resolve_request is None:
        raise InvariantViolationError("Resolve request upsert failed")
    return resolve_request
