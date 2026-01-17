"""Baseline schema.

Revision ID: 20250101_00
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op

from app.models import Base


revision = "20250101_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
