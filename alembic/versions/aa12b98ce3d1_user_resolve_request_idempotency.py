"""user resolve request idempotency

Revision ID: aa12b98ce3d1
Revises: 5b527241817b
Create Date: 2026-04-24 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa12b98ce3d1"
down_revision: Union[str, Sequence[str], None] = "5b527241817b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_resolve_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_request_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_request", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_request_id"),
    )
    op.create_index(
        "ix_user_resolve_requests_external_request_id",
        "user_resolve_requests",
        ["external_request_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_resolve_requests_external_request_id", table_name="user_resolve_requests")
    op.drop_table("user_resolve_requests")
