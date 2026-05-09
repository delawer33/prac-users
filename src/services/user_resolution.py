from uuid import UUID

from sqlalchemy.exc import IntegrityError

from src.exceptions import InvariantViolationError
from src.models.users import UserModel
from src.repositories.users import UsersRepository
from src.schemas.users import UserRead, UserResolveRequest, UserResolveResponse


class UserResolutionService:
    def __init__(self, repo: UsersRepository) -> None:
        self.repo = repo

    async def resolve(self, data: UserResolveRequest) -> UserResolveResponse:
        email = str(data.email)
        external_request_id = data.external_request_id

        replayed = await self._replay_resolve_request(external_request_id)
        if replayed:
            user, created_by_request = replayed
        else:
            user, created_by_request = await self._link_or_create_resolved_user(
                external_request_id,
                email,
            )

        return UserResolveResponse(
            user=UserRead.model_validate(user),
            created=created_by_request,
        )

    async def _replay_resolve_request(
        self,
        external_request_id: str,
    ) -> tuple[UserModel, bool] | None:
        # replay по external_request_id для ретраев
        existing_request = await self.repo.get_resolve_request(external_request_id)
        if not existing_request:
            return None
        user = await self.repo.get_user(existing_request.user_id)
        if user is None:
            raise InvariantViolationError("Resolve request points to missing user")
        return user, existing_request.created_by_request

    async def _link_or_create_resolved_user(
        self,
        external_request_id: str,
        email: str,
    ) -> tuple[UserModel, bool]:
        # если пользователь уже существует по email, только привязываем request-id
        existing_user = await self.repo.get_user_by_email(email)
        if existing_user:
            return await self._link_resolve_request(external_request_id, existing_user.id)

        # создаем/получаем пользователя и приводим его к active-состоянию
        try:
            new_user = await self.repo.create_resolved_user(email)
        except IntegrityError:
            # Гонка: пользователь появился между чтением и созданием
            raced_user = await self.repo.get_user_by_email(email)
            if not raced_user:
                raise
            return await self._link_resolve_request(
                external_request_id,
                raced_user.id,
                activate=True,
            )

        # Фиксируем связку request-id -> user
        resolve_request = await self.repo.create_resolve_request(
            external_request_id=external_request_id,
            user_id=new_user.id,
            created_by_request=True,
        )
        return new_user, resolve_request.created_by_request

    async def _link_resolve_request(
        self,
        external_request_id: str,
        user_id: UUID,
        *,
        activate: bool = False,
    ) -> tuple[UserModel, bool]:
        resolve_request = await self.repo.create_resolve_request(
            external_request_id=external_request_id,
            user_id=user_id,
            created_by_request=False,
        )
        user = await self.repo.get_user(resolve_request.user_id)
        if user is None:
            raise InvariantViolationError("Resolve request points to missing user")
        if activate:
            await self.repo.activate_user(user)
        return user, resolve_request.created_by_request
