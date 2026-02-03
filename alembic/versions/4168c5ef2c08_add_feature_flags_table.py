"""add feature flags table

Revision ID: 4168c5ef2c08
Revises: 42bd22621a75
Create Date: 2026-02-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4168c5ef2c08'
down_revision: Union[str, None] = '42bd22621a75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Boolean(), nullable=False),
        sa.Column("account_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # Standard btree indexes for common lookups
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])
    op.create_index("ix_feature_flags_account_id", "feature_flags", ["account_id"])

    # Partial unique indexes – enforce one global row per key and one
    # per-account row per key.  PostgreSQL NULL ≠ NULL semantics make a
    # single UniqueConstraint on (key, account_id) insufficient for the
    # global case, so two partial indexes are the idiomatic solution.
    op.execute(
        "CREATE UNIQUE INDEX ix_feature_flags_key_global "
        "ON feature_flags (key) WHERE account_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_feature_flags_key_account "
        "ON feature_flags (key, account_id) WHERE account_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_feature_flags_key_account")
    op.execute("DROP INDEX IF EXISTS ix_feature_flags_key_global")
    op.drop_index("ix_feature_flags_account_id", table_name="feature_flags")
    op.drop_index("ix_feature_flags_key", table_name="feature_flags")
    op.drop_table("feature_flags")
