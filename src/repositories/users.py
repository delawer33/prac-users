from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AlreadyExistsError
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
    try:
        await session.flush()
    except IntegrityError:
        raise AlreadyExistsError("email", email)
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
    try:
        await session.flush()
    except IntegrityError:
        raise AlreadyExistsError("email", email)
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


async def resolve_user_for_request(
    session: AsyncSession,
    *,
    external_request_id: str,
    email: str,
) -> tuple[UserModel, bool]:
    # replay по external_request_id для ретраев
    existing_request = await get_resolve_request(session, external_request_id)
    if existing_request:
        existing_user = await get_user(session, existing_request.user_id)
        if existing_user is None:
            raise RuntimeError("Resolve request points to missing user")
        return existing_user, existing_request.created_by_request

    # если пользователь уже существует по email, только привязываем request-id
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        resolve_request = await create_resolve_request(
            session=session,
            external_request_id=external_request_id,
            user_id=existing_user.id,
            created_by_request=False,
        )
        resolved_user = await get_user(session, resolve_request.user_id)
        if resolved_user is None:
            raise RuntimeError("Resolve request points to missing user")
        return resolved_user, resolve_request.created_by_request

    # создаем/получаем пользователя и приводим его к active-состоянию
    try:
        user = await create_resolved_user(session, email)
    except AlreadyExistsError:
        # Гонка: пользователь появился между чтением и созданием
        raced_user = await get_user_by_email(session, email)
        if not raced_user:
            raise
        resolve_request = await create_resolve_request(
            session=session,
            external_request_id=external_request_id,
            user_id=raced_user.id,
            created_by_request=False,
        )
        resolved_user = await get_user(session, resolve_request.user_id)
        if resolved_user is None:
            raise RuntimeError("Resolve request points to missing user")
        await activate_user(session, resolved_user)
        return resolved_user, resolve_request.created_by_request

    # Фиксируем связку request-id -> user
    resolve_request = await create_resolve_request(
        session=session,
        external_request_id=external_request_id,
        user_id=user.id,
        created_by_request=True,
    )
    return user, resolve_request.created_by_request
