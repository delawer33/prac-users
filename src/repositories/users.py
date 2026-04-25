from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import UserEmailAlreadyExistsError
from src.models.user_resolve_requests import UserResolveRequestModel
from src.models.users import UserModel
from src.schemas.users import UserCreate


async def get_user(session: AsyncSession, user_id: UUID) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, data: UserCreate) -> UserModel:
    user = UserModel(
        username=data.username,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise UserEmailAlreadyExistsError(str(data.email)) from exc
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
        is_active=False,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise UserEmailAlreadyExistsError(email) from exc
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: UserModel) -> None:
    await session.execute(
        delete(UserResolveRequestModel).where(UserResolveRequestModel.user_id == user.id)
    )
    await session.delete(user)
    await session.flush()


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
    request = UserResolveRequestModel(
        external_request_id=external_request_id,
        user_id=user_id,
        created_by_request=created_by_request,
    )
    session.add(request)
    try:
        await session.flush()
    except IntegrityError:
        existing = await get_resolve_request(session, external_request_id)
        if existing:
            return existing
        raise
    await session.refresh(request)
    return request


async def delete_resolve_request_by_external_id(
    session: AsyncSession,
    external_request_id: str,
) -> None:
    await session.execute(
        delete(UserResolveRequestModel).where(
            UserResolveRequestModel.external_request_id == external_request_id
        )
    )
    await session.flush()
