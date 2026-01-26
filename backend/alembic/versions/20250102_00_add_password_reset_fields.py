"""Add password reset fields to users.

Revision ID: 20250102_00
Revises: 20250101_03
Create Date: 2025-01-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20250102_00"
down_revision = "20250101_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reset_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
