"""add user stats columns and processed_messages table

Revision ID: 0002_user_stats_processed
Revises: 0001_users_squashed
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_stats_processed"
down_revision: Union[str, Sequence[str], None] = "0001_users_squashed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("orders_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("users", sa.Column("last_ordered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("total_spent", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "processed_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_processed_messages_event_id", "processed_messages", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_processed_messages_event_id", table_name="processed_messages")
    op.drop_table("processed_messages")
    op.drop_column("users", "total_spent")
    op.drop_column("users", "last_ordered_at")
    op.drop_column("users", "orders_count")
