"""Add persistent JWT token blacklist table.

Revision ID: 20260212_00
Revises: 20250129_00
Create Date: 2026-02-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260212_00"
down_revision: str | None = "20250129_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS token_blacklist (
                id SERIAL NOT NULL,
                jti VARCHAR(128) NOT NULL,
                token_type VARCHAR(20) NOT NULL DEFAULT 'access',
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                PRIMARY KEY (id),
                UNIQUE (jti)
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_token_blacklist_jti ON token_blacklist (jti)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_token_blacklist_expires_at ON token_blacklist (expires_at)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_token_blacklist_expires_at", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")
