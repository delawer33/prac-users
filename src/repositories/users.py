from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import InvariantViolationError
from src.models.user_resolve_requests import UserResolveRequestModel
from src.models.users import UserModel


class UsersRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user(self, user_id: UUID) -> UserModel | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        return result.scalar_one_or_none()

    async def upsert_user(
        self,
        *,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
    ) -> UUID | None:
        stmt = (
            pg_insert(UserModel)
            .values(
                id=uuid4(),
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(UserModel.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> UserModel | None:
        result = await self.db.execute(select(UserModel).where(UserModel.email == email))
        return result.scalar_one_or_none()

    async def upsert_resolved_user(self, email: str) -> UUID | None:
        stmt = (
            pg_insert(UserModel)
            .values(
                id=uuid4(),
                username=None,
                email=email,
                first_name=None,
                last_name=None,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(UserModel.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def activate_user(self, user: UserModel) -> UserModel:
        user.is_active = True
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def deactivate_user(self, user: UserModel) -> UserModel:
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def was_user_created_by_request(self, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(UserResolveRequestModel.id).where(
                UserResolveRequestModel.user_id == user_id,
                UserResolveRequestModel.created_by_request.is_(True),
            )
        )
        return result.first() is not None

    async def get_resolve_request(
        self,
        external_request_id: str,
    ) -> UserResolveRequestModel | None:
        result = await self.db.execute(
            select(UserResolveRequestModel).where(
                UserResolveRequestModel.external_request_id == external_request_id
            )
        )
        return result.scalar_one_or_none()

    async def increment_feedbacks_count(self, user_id: UUID) -> bool:
        result = await self.db.execute(
            sa.update(UserModel)
            .where(UserModel.id == user_id)
            .values(feedbacks_count=UserModel.feedbacks_count + 1)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def create_resolve_request(
        self,
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
        await self.db.execute(stmt)

        resolve_request = await self.get_resolve_request(external_request_id)
        if resolve_request is None:
            raise InvariantViolationError("Resolve request upsert failed")
        return resolve_request
