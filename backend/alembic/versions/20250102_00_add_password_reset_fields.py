"""Add password reset fields to users.

Revision ID: 20250102_00
Revises: 20250101_03
Create Date: 2025-01-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20250102_00"
down_revision = "20250101_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_hash VARCHAR(64)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires_at "
            "TIMESTAMP WITH TIME ZONE"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
