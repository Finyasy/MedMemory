"""Pydantic schemas for data ingestion API."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================
# Lab Results Schemas
# ============================================

class LabResultIngest(BaseModel):
    """Schema for ingesting a single lab result."""
    
    # Patient identification (one required)
    patient_id: Optional[int] = None
    patient_external_id: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    
    # Test info (required)
    test_name: str = Field(..., min_length=1, max_length=200)
    test_code: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    
    # Results
    value: Optional[str] = Field(None, max_length=100)
    numeric_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, pattern="^(normal|abnormal|critical|pending)$")
    
    # Timing
    collected_at: Optional[datetime] = None
    resulted_at: Optional[datetime] = None
    
    # Additional info
    notes: Optional[str] = None
    ordering_provider: Optional[str] = Field(None, max_length=200)
    performing_lab: Optional[str] = Field(None, max_length=200)
    source_system: Optional[str] = Field(None, max_length=100)
    source_id: Optional[str] = Field(None, max_length=100)


class LabResultResponse(BaseModel):
    """Response schema for lab result."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    patient_id: int
    test_name: str
    test_code: Optional[str] = None
    category: Optional[str] = None
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = None
    is_abnormal: bool
    collected_at: Optional[datetime] = None
    resulted_at: Optional[datetime] = None
    created_at: datetime


class LabPanelIngest(BaseModel):
    """Schema for ingesting a lab panel (multiple tests)."""
    
    patient_id: int
    panel_name: str = Field(..., min_length=1, max_length=200)
    collected_at: Optional[datetime] = None
    ordering_provider: Optional[str] = Field(None, max_length=200)
    results: list[LabResultIngest]


# ============================================
# Medication Schemas
# ============================================

class MedicationIngest(BaseModel):
    """Schema for ingesting a medication/prescription."""
    
    # Patient identification (one required)
    patient_id: Optional[int] = None
    patient_external_id: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    
    # Drug info (required)
    name: str = Field(..., min_length=1, max_length=200)
    generic_name: Optional[str] = Field(None, max_length=200)
    drug_code: Optional[str] = Field(None, max_length=50)
    drug_class: Optional[str] = Field(None, max_length=100)
    
    # Dosage
    dosage: Optional[str] = Field(None, max_length=100)
    dosage_value: Optional[float] = None
    dosage_unit: Optional[str] = Field(None, max_length=50)
    frequency: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    
    # Timing
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribed_at: Optional[datetime] = None
    
    # Status
    is_active: Optional[bool] = True
    status: Optional[str] = Field(None, pattern="^(active|completed|discontinued|on-hold|cancelled)$")
    discontinue_reason: Optional[str] = None
    
    # Prescription details
    prescriber: Optional[str] = Field(None, max_length=200)
    pharmacy: Optional[str] = Field(None, max_length=200)
    quantity: Optional[int] = None
    refills_remaining: Optional[int] = None
    
    # Additional info
    indication: Optional[str] = None
    instructions: Optional[str] = None
    notes: Optional[str] = None
    source_system: Optional[str] = Field(None, max_length=100)
    source_id: Optional[str] = Field(None, max_length=100)


class MedicationResponse(BaseModel):
    """Response schema for medication."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    patient_id: int
    name: str
    generic_name: Optional[str] = None
    drug_class: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool
    status: Optional[str] = None
    prescriber: Optional[str] = None
    indication: Optional[str] = None
    created_at: datetime


# ============================================
# Encounter Schemas
# ============================================

class VitalsIngest(BaseModel):
    """Schema for vital signs."""
    
    blood_pressure: Optional[str] = Field(None, max_length=20)
    heart_rate: Optional[int] = Field(None, ge=0, le=300)
    temperature: Optional[float] = Field(None, ge=90, le=110)
    weight: Optional[float] = Field(None, ge=0)
    height: Optional[float] = Field(None, ge=0)
    bmi: Optional[float] = Field(None, ge=0, le=100)
    oxygen_saturation: Optional[float] = Field(None, ge=0, le=100)


class EncounterIngest(BaseModel):
    """Schema for ingesting a medical encounter/visit."""
    
    # Patient identification (one required)
    patient_id: Optional[int] = None
    patient_external_id: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    
    # Encounter info
    encounter_type: str = Field(default="office_visit", max_length=50)
    encounter_date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Location
    facility: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    # Provider
    provider_name: Optional[str] = Field(None, max_length=200)
    provider_specialty: Optional[str] = Field(None, max_length=100)
    
    # Clinical
    chief_complaint: Optional[str] = None
    reason_for_visit: Optional[str] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    follow_up: Optional[str] = None
    clinical_notes: Optional[str] = None
    diagnoses: Optional[list[str]] = None
    
    # Vitals
    vitals: Optional[VitalsIngest] = None
    
    # Status
    status: Optional[str] = Field(default="completed")
    
    # Source
    source_system: Optional[str] = Field(None, max_length=100)
    source_id: Optional[str] = Field(None, max_length=100)


class EncounterResponse(BaseModel):
    """Response schema for encounter."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    patient_id: int
    encounter_type: str
    encounter_date: datetime
    provider_name: Optional[str] = None
    provider_specialty: Optional[str] = None
    facility: Optional[str] = None
    chief_complaint: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    status: str
    vital_blood_pressure: Optional[str] = None
    vital_heart_rate: Optional[int] = None
    vital_temperature: Optional[float] = None
    created_at: datetime


# ============================================
# Batch Ingestion Schemas
# ============================================

class BatchIngestionRequest(BaseModel):
    """Request for batch ingestion of multiple record types."""
    
    labs: Optional[list[LabResultIngest]] = None
    medications: Optional[list[MedicationIngest]] = None
    encounters: Optional[list[EncounterIngest]] = None


class IngestionResultResponse(BaseModel):
    """Response for ingestion operations."""
    
    success: bool
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: list[str] = []
    timestamp: datetime
