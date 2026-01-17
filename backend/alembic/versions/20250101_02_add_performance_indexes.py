"""Add performance indexes for common queries.

Revision ID: 20250101_02
Revises: 20250101_01
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20250101_02"
down_revision = "20250101_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use IF NOT EXISTS to handle cases where indexes may already exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_patients_user_last_first 
        ON patients (user_id, last_name, first_name)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_documents_patient_received 
        ON documents (patient_id, received_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_records_patient_created 
        ON records (patient_id, created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_memory_chunks_patient_created 
        ON memory_chunks (patient_id, created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lab_results_patient_collected 
        ON lab_results (patient_id, collected_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_medications_patient_prescribed 
        ON medications (patient_id, prescribed_at)
    """)


def downgrade() -> None:
    op.drop_index("ix_medications_patient_prescribed", table_name="medications")
    op.drop_index("ix_lab_results_patient_collected", table_name="lab_results")
    op.drop_index("ix_memory_chunks_patient_created", table_name="memory_chunks")
    op.drop_index("ix_records_patient_created", table_name="records")
    op.drop_index("ix_documents_patient_received", table_name="documents")
    op.drop_index("ix_patients_user_last_first", table_name="patients")
