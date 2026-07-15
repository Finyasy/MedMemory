"""Add OCR refinement fields to documents.

Revision ID: 20250101_03
Revises: 20250101_02
Create Date: 2025-01-01 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "20250101_03"
down_revision = "20250101_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_text_raw TEXT"))
    op.execute(
        sa.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_text_cleaned TEXT")
    )
    op.execute(sa.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_entities TEXT"))


def downgrade() -> None:
    op.drop_column("documents", "ocr_entities")
    op.drop_column("documents", "ocr_text_cleaned")
    op.drop_column("documents", "ocr_text_raw")
