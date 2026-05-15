"""initial users and resolve requests schema

Revision ID: 0001_users_squashed
Revises:
Create Date: 2026-05-01 13:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_users_squashed"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_resolve_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_request_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_request", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
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
    op.drop_index("ix_user_resolve_requests_external_request_id", table_name="user_resolve_requests")
    op.drop_table("user_resolve_requests")
    op.drop_table("users")
