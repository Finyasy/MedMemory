"""Add user ownership to patients.

Revision ID: 20250101_01
Revises: 20250101_00
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20250101_01"
down_revision = "20250101_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("patients")}

    if "user_id" not in columns:
        op.add_column(
            "patients",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_patients_user_id", "patients", ["user_id"])
        op.create_foreign_key(
            "fk_patients_user_id_users",
            "patients",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute("ALTER TABLE patients ALTER COLUMN user_id SET DEFAULT NULL")

    op.execute(
        """
        DO $$
        DECLARE
            owner_id INTEGER;
        BEGIN
            SELECT id INTO owner_id FROM users ORDER BY id ASC LIMIT 1;
            IF owner_id IS NULL THEN
                INSERT INTO users (email, hashed_password, full_name, is_active, created_at, updated_at)
                VALUES (
                    'system@medmemory.local',
                    '$2b$12$C6UzMDM.H6dfI/f/IKcEe.6.J8mEV6rBdlilx2O2FNRgYB8V3QG6e',
                    'System User',
                    FALSE,
                    NOW(),
                    NOW()
                )
                RETURNING id INTO owner_id;
            END IF;

            UPDATE patients SET user_id = owner_id WHERE user_id IS NULL;
        END $$;
        """
    )

    op.alter_column("patients", "user_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_patients_user_id_users", "patients", type_="foreignkey")
    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_column("patients", "user_id")
