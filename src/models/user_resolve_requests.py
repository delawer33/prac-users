from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class UserResolveRequestModel(Base):
    __tablename__ = "user_resolve_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_request_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True, index=True)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_request: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
