"""API Routes for MedMemory."""

from app.api import (
    auth,
    chat,
    clinician,
    context,
    dashboard,
    dependents,
    documents,
    health,
    ingestion,
    insights,
    memory,
    patient_access,
    patients,
    profile,
    records,
)

__all__ = [
    "auth",
    "chat",
    "context",
    "dashboard",
    "documents",
    "health",
    "ingestion",
    "memory",
    "patients",
    "records",
    "insights",
    "profile",
    "dependents",
    "clinician",
    "patient_access",
]
