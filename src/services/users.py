import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import (
    AlreadyExistsError,
    InvariantViolationError,
    NotFoundError,
)
from src.models.users import UserModel
from src.repositories import users as users_repo
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse

logger = logging.getLogger(__name__)


async def get_user(session: AsyncSession, user_id: UUID) -> UserRead:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise NotFoundError(f"User not found: {user_id}")
    return UserRead.model_validate(user)


async def create_user(session: AsyncSession, data: UserCreate) -> UserRead:
    try:
        user = await users_repo.create_user(
            session,
            username=data.username,
            email=str(data.email),
            first_name=data.first_name,
            last_name=data.last_name,
        )
    except IntegrityError:
        raise AlreadyExistsError("email", str(data.email))
    logger.info("user created user_id=%s", user.id)
    return UserRead.model_validate(user)


async def resolve_user(session: AsyncSession, data: UserResolveRequest) -> UserResolveResponse:
    email = str(data.email)
    external_request_id = data.external_request_id

    replayed = await _replay_resolve_request(session, external_request_id)
    if replayed:
        user, created_by_request = replayed
    else:
        user, created_by_request = await _link_or_create_resolved_user(session, external_request_id, email)

    logger.info(
        "user resolved user_id=%s external_request_id=%s created=%s",
        user.id,
        external_request_id,
        created_by_request,
    )
    return UserResolveResponse(
        user=UserRead.model_validate(user),
        created=created_by_request,
    )


async def _replay_resolve_request(
    session: AsyncSession,
    external_request_id: str,
) -> tuple[UserModel, bool] | None:
    # replay по external_request_id для ретраев
    existing_request = await users_repo.get_resolve_request(session, external_request_id)
    if not existing_request:
        return None
    user = await users_repo.get_user(session, existing_request.user_id)
    if user is None:
        raise InvariantViolationError("Resolve request points to missing user")
    return user, existing_request.created_by_request


async def _link_or_create_resolved_user(
    session: AsyncSession,
    external_request_id: str,
    email: str,
) -> tuple[UserModel, bool]:
    # если пользователь уже существует по email, только привязываем request-id
    existing_user = await users_repo.get_user_by_email(session, email)
    if existing_user:
        return await _link_resolve_request(session, external_request_id, existing_user.id)

    # создаем/получаем пользователя и приводим его к active-состоянию
    try:
        new_user = await users_repo.create_resolved_user(session, email)
    except IntegrityError:
        # Гонка: пользователь появился между чтением и созданием
        raced_user = await users_repo.get_user_by_email(session, email)
        if not raced_user:
            raise
        return await _link_resolve_request(session, external_request_id, raced_user.id, activate=True)

    # Фиксируем связку request-id -> user
    resolve_request = await users_repo.create_resolve_request(
        session=session,
        external_request_id=external_request_id,
        user_id=new_user.id,
        created_by_request=True,
    )
    return new_user, resolve_request.created_by_request


async def _link_resolve_request(
    session: AsyncSession,
    external_request_id: str,
    user_id: UUID,
    *,
    activate: bool = False,
) -> tuple[UserModel, bool]:
    resolve_request = await users_repo.create_resolve_request(
        session=session,
        external_request_id=external_request_id,
        user_id=user_id,
        created_by_request=False,
    )
    user = await users_repo.get_user(session, resolve_request.user_id)
    if user is None:
        raise InvariantViolationError("Resolve request points to missing user")
    if activate:
        await users_repo.activate_user(session, user)
    return user, resolve_request.created_by_request


async def cancel_user_for_order_saga(session: AsyncSession, user_id: UUID) -> None:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise NotFoundError(f"User not found: {user_id}")

    if await users_repo.was_user_created_by_request(session, user_id):
        await users_repo.deactivate_user(session, user)

    logger.info("user saga cancellation processed user_id=%s", user_id)
