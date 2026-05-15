import logging
from uuid import UUID

from src.exceptions import AlreadyExistsError, InvariantViolationError, NotFoundError
from src.repositories.users import UsersRepository
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse
from src.services.user_resolution import UserResolutionService

logger = logging.getLogger(__name__)


class UsersService:
    def __init__(self, repo: UsersRepository) -> None:
        self.repo = repo
        self._resolution = UserResolutionService(repo)

    async def get_user(self, user_id: UUID) -> UserRead:
        user = await self.repo.get_user(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")
        return UserRead.model_validate(user)

    async def create_user(self, data: UserCreate) -> UserRead:
        inserted_id = await self.repo.upsert_user(
            username=data.username,
            email=str(data.email),
            first_name=data.first_name,
            last_name=data.last_name,
        )
        if inserted_id is None:
            raise AlreadyExistsError("email", str(data.email))
        user = await self.repo.get_user(inserted_id)
        if user is None:
            raise InvariantViolationError("User insert returned unknown id")
        logger.info("user created user_id=%s", user.id)
        return UserRead.model_validate(user)

    async def resolve_user(self, data: UserResolveRequest) -> UserResolveResponse:
        response = await self._resolution.resolve(data)
        logger.info(
            "user resolved user_id=%s external_request_id=%s created=%s",
            response.user.id,
            data.external_request_id,
            response.created,
        )
        return response

    async def cancel_user_for_order_saga(self, user_id: UUID) -> None:
        user = await self.repo.get_user(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        if await self.repo.was_user_created_by_request(user_id):
            await self.repo.deactivate_user(user)

        logger.info("user saga cancellation processed user_id=%s", user_id)
