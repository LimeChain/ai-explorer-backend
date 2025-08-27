"""enable_pgvector_extension

Revision ID: fc53479d7923
Revises: 13f9da3db90d
Create Date: 2025-08-14 17:09:26.497442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc53479d7923'
down_revision: Union[str, Sequence[str], None] = '13f9da3db90d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector extension for vector similarity search."""
    # Enable the pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Disable pgvector extension."""
    # Drop the pgvector extension (only if no tables use it)
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")
