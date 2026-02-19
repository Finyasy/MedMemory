"""Add comprehensive profile and dependents tables

Revision ID: 20250126_00
Revises: 20250102_00
Create Date: 2026-01-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20250126_00"
down_revision: str | None = "20250102_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new columns to patients table
    op.add_column("patients", sa.Column("sex", sa.String(20), nullable=True))
    op.add_column("patients", sa.Column("height_cm", sa.Numeric(5, 2), nullable=True))
    op.add_column("patients", sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "patients",
        sa.Column(
            "preferred_language", sa.String(10), server_default="en", nullable=True
        ),
    )
    op.add_column("patients", sa.Column("timezone", sa.String(50), nullable=True))
    op.add_column(
        "patients", sa.Column("profile_photo_url", sa.String(500), nullable=True)
    )
    op.add_column(
        "patients",
        sa.Column("is_dependent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "patients", sa.Column("profile_completed_at", sa.DateTime(), nullable=True)
    )

    # Emergency information table
    op.create_table(
        "patient_emergency_info",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("medical_alert", sa.Text(), nullable=True),
        sa.Column("organ_donor", sa.Boolean(), nullable=True),
        sa.Column("dnr_status", sa.Boolean(), nullable=True),
        sa.Column("preferred_hospital", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id"),
    )

    # Emergency contacts table
    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("priority_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_emergency_contacts_patient", "emergency_contacts", ["patient_id"]
    )

    # Allergies table
    op.create_table(
        "patient_allergies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("allergen", sa.String(255), nullable=False),
        sa.Column("allergy_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("reaction", sa.Text(), nullable=True),
        sa.Column("diagnosed_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_allergies_patient", "patient_allergies", ["patient_id"])

    # Chronic conditions table
    op.create_table(
        "patient_conditions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("condition_name", sa.String(255), nullable=False),
        sa.Column("icd_code", sa.String(20), nullable=True),
        sa.Column("diagnosed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("treating_physician", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patient_conditions_patient", "patient_conditions", ["patient_id"]
    )

    # Healthcare providers table
    op.create_table(
        "patient_providers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("clinic_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("fax", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_providers_patient", "patient_providers", ["patient_id"])

    # Lifestyle factors table
    op.create_table(
        "patient_lifestyle",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("smoking_status", sa.String(20), nullable=True),
        sa.Column("smoking_frequency", sa.String(50), nullable=True),
        sa.Column("alcohol_use", sa.String(20), nullable=True),
        sa.Column("exercise_frequency", sa.String(20), nullable=True),
        sa.Column("diet_type", sa.String(50), nullable=True),
        sa.Column("sleep_hours", sa.Numeric(3, 1), nullable=True),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("stress_level", sa.String(20), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id"),
    )

    # Insurance information table
    op.create_table(
        "patient_insurance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(255), nullable=False),
        sa.Column("policy_number", sa.String(100), nullable=True),
        sa.Column("group_number", sa.String(100), nullable=True),
        sa.Column("subscriber_name", sa.String(255), nullable=True),
        sa.Column("subscriber_dob", sa.Date(), nullable=True),
        sa.Column("relationship_to_subscriber", sa.String(50), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_insurance_patient", "patient_insurance", ["patient_id"])

    # Family medical history table
    op.create_table(
        "family_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(50), nullable=False),
        sa.Column("condition", sa.String(255), nullable=False),
        sa.Column("age_of_onset", sa.Integer(), nullable=True),
        sa.Column("is_deceased", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_family_history_patient", "family_history", ["patient_id"])

    # Child-specific: Vaccinations table
    op.create_table(
        "patient_vaccinations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("vaccine_name", sa.String(255), nullable=False),
        sa.Column("dose_number", sa.Integer(), nullable=True),
        sa.Column("date_administered", sa.Date(), nullable=False),
        sa.Column("administered_by", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("lot_number", sa.String(100), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("site", sa.String(50), nullable=True),
        sa.Column("reaction", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patient_vaccinations_patient", "patient_vaccinations", ["patient_id"]
    )

    # Child-specific: Growth measurements table
    op.create_table(
        "growth_measurements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("measurement_date", sa.Date(), nullable=False),
        sa.Column("age_months", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("head_circumference_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("height_percentile", sa.Integer(), nullable=True),
        sa.Column("weight_percentile", sa.Integer(), nullable=True),
        sa.Column("bmi", sa.Numeric(4, 2), nullable=True),
        sa.Column("bmi_percentile", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_growth_measurements_patient", "growth_measurements", ["patient_id"]
    )

    # Patient relationships (for dependents)
    op.create_table(
        "patient_relationships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("caretaker_patient_id", sa.Integer(), nullable=False),
        sa.Column("dependent_patient_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column(
            "is_primary_caretaker", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("can_edit", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_share", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["caretaker_patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dependent_patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("caretaker_patient_id", "dependent_patient_id"),
    )
    op.create_index(
        "ix_patient_relationships_caretaker",
        "patient_relationships",
        ["caretaker_patient_id"],
    )
    op.create_index(
        "ix_patient_relationships_dependent",
        "patient_relationships",
        ["dependent_patient_id"],
    )


def downgrade() -> None:
    op.drop_table("patient_relationships")
    op.drop_table("growth_measurements")
    op.drop_table("patient_vaccinations")
    op.drop_table("family_history")
    op.drop_table("patient_insurance")
    op.drop_table("patient_lifestyle")
    op.drop_table("patient_providers")
    op.drop_table("patient_conditions")
    op.drop_table("patient_allergies")
    op.drop_table("emergency_contacts")
    op.drop_table("patient_emergency_info")

    op.drop_column("patients", "profile_completed_at")
    op.drop_column("patients", "is_dependent")
    op.drop_column("patients", "profile_photo_url")
    op.drop_column("patients", "timezone")
    op.drop_column("patients", "preferred_language")
    op.drop_column("patients", "weight_kg")
    op.drop_column("patients", "height_cm")
    op.drop_column("patients", "sex")
