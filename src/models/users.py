from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class UserModel(Base):
    __tablename__ = 'users'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    email: Mapped[str] = mapped_column(sa.String(), unique=True)
    first_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), default=True, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    feedbacks_count: Mapped[int] = mapped_column(
        sa.Integer(), nullable=False, default=0, server_default=sa.text("0")
    )
