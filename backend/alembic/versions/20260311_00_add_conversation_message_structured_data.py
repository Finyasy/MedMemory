"""Persist structured chat payloads on conversation messages.

Revision ID: 20260311_00
Revises: 20260307_00
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260311_00"
down_revision: str | None = "20260307_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS "
            "structured_data_json TEXT"
        )
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "structured_data_json")
