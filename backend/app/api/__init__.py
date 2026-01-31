"""API Routes for MedMemory."""

from app.api import auth, chat, context, documents, health, ingestion, memory, patients, records, insights, profile, dependents, clinician, patient_access

__all__ = [
    "auth",
    "chat",
    "context",
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
