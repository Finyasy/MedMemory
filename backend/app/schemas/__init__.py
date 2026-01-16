"""Pydantic schemas for API request/response validation."""

from app.schemas.patient import (
    PatientBase,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientSummary,
)
from app.schemas.records import (
    RecordBase,
    RecordCreate,
    RecordResponse,
)

__all__ = [
    # Patient
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientSummary",
    # Records (legacy)
    "RecordBase",
    "RecordCreate",
    "RecordResponse",
]
