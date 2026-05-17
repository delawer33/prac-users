import os
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models import metadata
from src.models.users import UserModel

TEST_DB_URL = os.getenv("TEST_POSTGRES_URL", "postgresql+asyncpg://postgres:123456@localhost:5432/users_test")


async def _make_session() -> AsyncGenerator[AsyncSession, None]:
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(metadata.create_all)
    session_maker = async_sessionmaker(eng, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    async with eng.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            await conn.execute(sa.delete(table))
    await eng.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in _make_session():
        yield session


async def create_user(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    email: str = "test@example.com",
) -> UserModel:
    user = UserModel(
        id=user_id or uuid4(),
        email=email,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
