import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import UserDeletionForbiddenError, UserEmailAlreadyExistsError, UserNotFoundError
from src.repositories import users as users_repo
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse

logger = logging.getLogger(__name__)


async def get_user(session: AsyncSession, user_id: UUID) -> UserRead:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return UserRead.model_validate(user)


async def create_user(session: AsyncSession, data: UserCreate) -> UserRead:
    user = await users_repo.create_user(session, data)
    logger.info("user created user_id=%s", user.id)
    return UserRead.model_validate(user)


async def resolve_user(session: AsyncSession, data: UserResolveRequest) -> UserResolveResponse:
    existing_request = await users_repo.get_resolve_request(session, data.external_request_id)
    if existing_request:
        existing_user = await users_repo.get_user(session, existing_request.user_id)
        if existing_user:
            return UserResolveResponse(
                user=UserRead.model_validate(existing_user),
                created=existing_request.created_by_request,
            )
        logger.warning(
            "stale resolve request detected external_request_id=%s user_id=%s",
            data.external_request_id,
            existing_request.user_id,
        )
        await users_repo.delete_resolve_request_by_external_id(
            session=session,
            external_request_id=data.external_request_id,
        )

    existing_user = await users_repo.get_user_by_email(session, str(data.email))
    if existing_user:
        # Привязываем request id к уже существующему пользователю для стабильных ретраев
        resolve_request = await users_repo.create_resolve_request(
            session=session,
            external_request_id=data.external_request_id,
            user_id=existing_user.id,
            created_by_request=False,
        )
        resolved_user = await users_repo.get_user(session, resolve_request.user_id)
        if not resolved_user:
            raise UserNotFoundError(resolve_request.user_id)
        return UserResolveResponse(
            user=UserRead.model_validate(resolved_user),
            created=resolve_request.created_by_request,
        )

    try:
        # Создаем неактивного временного пользователя; при сбое создания заказа
        # воркер orders может выполнить компенсацию (удаление)
        user = await users_repo.create_resolved_user(session, str(data.email))
    except UserEmailAlreadyExistsError:
        # Если пользователь существует (конкурентный запрос создал),
        # связываем request-id с существующим пользователем
        raced_user = await users_repo.get_user_by_email(session, str(data.email))
        if not raced_user:
            raise
        resolve_request = await users_repo.create_resolve_request(
            session=session,
            external_request_id=data.external_request_id,
            user_id=raced_user.id,
            created_by_request=False,
        )
        resolved_user = await users_repo.get_user(session, resolve_request.user_id)
        if not resolved_user:
            raise UserNotFoundError(resolve_request.user_id)
        return UserResolveResponse(
            user=UserRead.model_validate(resolved_user),
            created=resolve_request.created_by_request,
        )

    resolve_request = await users_repo.create_resolve_request(
        session=session,
        external_request_id=data.external_request_id,
        user_id=user.id,
        created_by_request=True,
    )
    resolved_user = await users_repo.get_user(session, resolve_request.user_id)
    if not resolved_user:
        raise UserNotFoundError(resolve_request.user_id)
    logger.info("user resolved user_id=%s email=%s created=%s", resolved_user.id, data.email, resolve_request.created_by_request)
    return UserResolveResponse(
        user=UserRead.model_validate(resolved_user),
        created=resolve_request.created_by_request,
    )


async def delete_user(session: AsyncSession, user_id: UUID) -> None:
    user = await users_repo.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)
    if user.is_active:
        raise UserDeletionForbiddenError(user_id)

    await users_repo.delete_user(session, user)
    logger.info("inactive user deleted user_id=%s", user_id)
