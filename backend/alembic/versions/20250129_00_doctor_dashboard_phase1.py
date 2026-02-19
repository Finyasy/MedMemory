"""Doctor dashboard Phase 1: user role, clinician profiles, access grants, audit log.

Revision ID: 20250129_00
Revises: 20250126_00
Create Date: 2026-01-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "20250129_00"
down_revision: str | None = "20250126_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(conn, name: str) -> bool:
    return inspect(conn).has_table(name)


def _column_exists(conn, table: str, column: str) -> bool:
    return column in (c["name"] for c in inspect(conn).get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    # users.role: idempotent
    if not _column_exists(conn, "users", "role"):
        op.add_column(
            "users",
            sa.Column("role", sa.String(20), server_default="patient", nullable=False),
        )
        op.execute(sa.text("UPDATE users SET role = 'patient' WHERE role IS NULL"))

    # clinician_profiles: raw SQL so "already exists" never fails
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS clinician_profiles (
            id SERIAL NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            npi VARCHAR(20),
            license_number VARCHAR(100),
            specialty VARCHAR(255),
            organization_name VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            verified_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (user_id)
        )
    """)
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_clinician_profiles_user_id ON clinician_profiles (user_id)"
        )
    )

    # patient_access_grants: idempotent
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS patient_access_grants (
            id SERIAL NOT NULL,
            patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            clinician_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            granted_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            scopes VARCHAR(255) NOT NULL DEFAULT 'documents,records,labs,medications,chat',
            granted_at TIMESTAMP WITH TIME ZONE,
            expires_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_patient_access_grants_patient_id ON patient_access_grants (patient_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_patient_access_grants_clinician_user_id ON patient_access_grants (clinician_user_id)"
        )
    )

    # access_audit_log: idempotent
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS access_audit_log (
            id SERIAL NOT NULL,
            actor_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            action VARCHAR(64) NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_access_audit_log_actor_user_id ON access_audit_log (actor_user_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_access_audit_log_patient_id ON access_audit_log (patient_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_access_audit_log_created_at ON access_audit_log (created_at)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_access_audit_log_created_at", table_name="access_audit_log")
    op.drop_index("ix_access_audit_log_patient_id", table_name="access_audit_log")
    op.drop_index("ix_access_audit_log_actor_user_id", table_name="access_audit_log")
    op.drop_table("access_audit_log")
    op.drop_index(
        "ix_patient_access_grants_clinician_user_id", table_name="patient_access_grants"
    )
    op.drop_index(
        "ix_patient_access_grants_patient_id", table_name="patient_access_grants"
    )
    op.drop_table("patient_access_grants")
    op.drop_index("ix_clinician_profiles_user_id", table_name="clinician_profiles")
    op.drop_table("clinician_profiles")
    op.drop_column("users", "role")
