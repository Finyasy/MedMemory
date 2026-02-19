"""Switch memory chunk vector index from IVFFlat to HNSW.

Revision ID: 20260214_00
Revises: 20260212_00
Create Date: 2026-02-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260214_00"
down_revision: str | None = "20260212_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_memory_chunks_embedding"))
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding
            ON memory_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 128)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_memory_chunks_embedding"))
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding
            ON memory_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
    )
