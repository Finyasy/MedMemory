"""Pydantic schemas for data ingestion API."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LabResultIngest(BaseModel):
    """Schema for ingesting a single lab result."""

    patient_id: int | None = None
    patient_external_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    test_name: str = Field(..., min_length=1, max_length=200)
    test_code: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    value: str | None = Field(None, max_length=100)
    numeric_value: float | None = None
    unit: str | None = Field(None, max_length=50)
    reference_range: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern="^(normal|abnormal|critical|pending)$")
    collected_at: datetime | None = None
    resulted_at: datetime | None = None
    notes: str | None = None
    ordering_provider: str | None = Field(None, max_length=200)
    performing_lab: str | None = Field(None, max_length=200)
    source_system: str | None = Field(None, max_length=100)
    source_id: str | None = Field(None, max_length=100)


class LabResultResponse(BaseModel):
    """Response schema for lab result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    test_name: str
    test_code: str | None = None
    category: str | None = None
    value: str | None = None
    numeric_value: float | None = None
    unit: str | None = None
    reference_range: str | None = None
    status: str | None = None
    is_abnormal: bool
    collected_at: datetime | None = None
    resulted_at: datetime | None = None
    created_at: datetime


class LabPanelIngest(BaseModel):
    """Schema for ingesting a lab panel (multiple tests)."""

    patient_id: int
    panel_name: str = Field(..., min_length=1, max_length=200)
    collected_at: datetime | None = None
    ordering_provider: str | None = Field(None, max_length=200)
    results: list[LabResultIngest]


class MedicationIngest(BaseModel):
    """Schema for ingesting a medication/prescription."""

    # Patient identification (one required)
    patient_id: int | None = None
    patient_external_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None

    # Drug info (required)
    name: str = Field(..., min_length=1, max_length=200)
    generic_name: str | None = Field(None, max_length=200)
    drug_code: str | None = Field(None, max_length=50)
    drug_class: str | None = Field(None, max_length=100)

    # Dosage
    dosage: str | None = Field(None, max_length=100)
    dosage_value: float | None = None
    dosage_unit: str | None = Field(None, max_length=50)
    frequency: str | None = Field(None, max_length=100)
    route: str | None = Field(None, max_length=50)

    # Timing
    start_date: date | None = None
    end_date: date | None = None
    prescribed_at: datetime | None = None

    # Status
    is_active: bool | None = True
    status: str | None = Field(
        None, pattern="^(active|completed|discontinued|on-hold|cancelled)$"
    )
    discontinue_reason: str | None = None

    # Prescription details
    prescriber: str | None = Field(None, max_length=200)
    pharmacy: str | None = Field(None, max_length=200)
    quantity: int | None = None
    refills_remaining: int | None = None

    # Additional info
    indication: str | None = None
    instructions: str | None = None
    notes: str | None = None
    source_system: str | None = Field(None, max_length=100)
    source_id: str | None = Field(None, max_length=100)


class MedicationResponse(BaseModel):
    """Response schema for medication."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    name: str
    generic_name: str | None = None
    drug_class: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool
    status: str | None = None
    prescriber: str | None = None
    indication: str | None = None
    created_at: datetime


class VitalsIngest(BaseModel):
    """Schema for vital signs."""

    blood_pressure: str | None = Field(None, max_length=20)
    heart_rate: int | None = Field(None, ge=0, le=300)
    temperature: float | None = Field(None, ge=90, le=110)
    weight: float | None = Field(None, ge=0)
    height: float | None = Field(None, ge=0)
    bmi: float | None = Field(None, ge=0, le=100)
    oxygen_saturation: float | None = Field(None, ge=0, le=100)


class EncounterIngest(BaseModel):
    """Schema for ingesting a medical encounter/visit."""

    patient_id: int | None = None
    patient_external_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    encounter_type: str = Field(default="office_visit", max_length=50)
    encounter_date: datetime
    start_time: datetime | None = None
    end_time: datetime | None = None
    facility: str | None = Field(None, max_length=200)
    department: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=200)
    provider_name: str | None = Field(None, max_length=200)
    provider_specialty: str | None = Field(None, max_length=100)
    chief_complaint: str | None = None
    reason_for_visit: str | None = None
    subjective: str | None = None
    objective: str | None = None
    assessment: str | None = None
    plan: str | None = None
    follow_up: str | None = None
    clinical_notes: str | None = None
    diagnoses: list[str] | None = None
    vitals: VitalsIngest | None = None
    status: str | None = Field(default="completed")
    source_system: str | None = Field(None, max_length=100)
    source_id: str | None = Field(None, max_length=100)


class EncounterResponse(BaseModel):
    """Response schema for encounter."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    encounter_type: str
    encounter_date: datetime
    provider_name: str | None = None
    provider_specialty: str | None = None
    facility: str | None = None
    chief_complaint: str | None = None
    assessment: str | None = None
    plan: str | None = None
    status: str
    vital_blood_pressure: str | None = None
    vital_heart_rate: int | None = None
    vital_temperature: float | None = None
    created_at: datetime


class BatchIngestionRequest(BaseModel):
    """Request for batch ingestion of multiple record types."""

    labs: list[LabResultIngest] | None = None
    medications: list[MedicationIngest] | None = None
    encounters: list[EncounterIngest] | None = None


class IngestionResultResponse(BaseModel):
    """Response for ingestion operations."""

    success: bool
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: list[str] = []
    timestamp: datetime
