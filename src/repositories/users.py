from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    await session.flush()
    await session.refresh(user)
    return user
