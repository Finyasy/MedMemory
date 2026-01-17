"""Encounters/visits ingestion service."""

import json
from datetime import datetime, timezone
from typing import Optional

from app.models import Encounter
from app.services.ingestion.base import IngestionService


class EncounterIngestionService(IngestionService[Encounter]):
    """Service for ingesting medical encounter/visit data.
    
    Supports various encounter data formats including SOAP notes,
    visit summaries, and structured clinical data.
    
    Example input format:
    {
        "patient_id": 1,
        "encounter_type": "office_visit",
        "encounter_date": "2024-01-15T10:00:00",
        "provider_name": "Dr. Smith",
        "provider_specialty": "Internal Medicine",
        "facility": "City Medical Center",
        "department": "Primary Care",
        "chief_complaint": "Annual physical exam",
        "reason_for_visit": "Routine checkup",
        "subjective": "Patient reports feeling well...",
        "objective": "Vitals: BP 120/80, HR 72, Temp 98.6F...",
        "assessment": "Healthy adult, well-controlled hypertension",
        "plan": "Continue current medications, follow up in 1 year",
        "diagnoses": ["Z00.00 - Annual physical exam", "I10 - Essential hypertension"],
        "vitals": {
            "blood_pressure": "120/80",
            "heart_rate": 72,
            "temperature": 98.6,
            "weight": 180,
            "height": 70,
            "bmi": 25.8,
            "oxygen_saturation": 98
        }
    }
    """
    
    VALID_ENCOUNTER_TYPES = [
        "office_visit", "emergency", "telehealth", "inpatient",
        "outpatient", "urgent_care", "home_visit", "lab_visit",
        "imaging", "procedure", "consultation", "follow_up"
    ]
    
    VALID_STATUSES = ["scheduled", "in-progress", "completed", "cancelled", "no-show"]
    
    async def ingest_single(self, data: dict) -> Encounter:
        """Ingest a single encounter record.
        
        Args:
            data: Dictionary containing encounter data
            
        Returns:
            Created Encounter model instance
        """
        # Get or validate patient
        patient = await self.get_or_create_patient(
            patient_id=data.get("patient_id"),
            external_id=data.get("patient_external_id"),
            first_name=data.get("patient_first_name"),
            last_name=data.get("patient_last_name"),
        )
        
        # Parse encounter date (required)
        encounter_date = self.parse_datetime(data.get("encounter_date"))
        if not encounter_date:
            encounter_date = datetime.now(timezone.utc)
        
        # Normalize encounter type
        encounter_type = self._normalize_encounter_type(
            data.get("encounter_type", "office_visit")
        )
        
        # Parse vitals
        vitals = data.get("vitals", {})
        
        # Parse diagnoses to JSON string
        diagnoses = data.get("diagnoses")
        if diagnoses and isinstance(diagnoses, list):
            diagnoses = json.dumps(diagnoses)
        
        # Build clinical notes from SOAP if not provided directly
        clinical_notes = data.get("clinical_notes")
        if not clinical_notes:
            clinical_notes = self._build_clinical_notes(data)
        
        # Create encounter
        encounter = Encounter(
            patient_id=patient.id,
            encounter_type=encounter_type,
            encounter_date=encounter_date,
            start_time=self.parse_datetime(data.get("start_time")),
            end_time=self.parse_datetime(data.get("end_time")),
            facility=data.get("facility"),
            department=data.get("department"),
            location=data.get("location"),
            provider_name=data.get("provider_name"),
            provider_specialty=data.get("provider_specialty"),
            chief_complaint=data.get("chief_complaint"),
            reason_for_visit=data.get("reason_for_visit"),
            diagnoses=diagnoses,
            assessment=data.get("assessment"),
            plan=data.get("plan"),
            follow_up=data.get("follow_up"),
            subjective=data.get("subjective"),
            objective=data.get("objective"),
            clinical_notes=clinical_notes,
            # Vitals
            vital_blood_pressure=vitals.get("blood_pressure") or data.get("vital_blood_pressure"),
            vital_heart_rate=self._parse_int(vitals.get("heart_rate") or data.get("vital_heart_rate")),
            vital_temperature=self.parse_float(vitals.get("temperature") or data.get("vital_temperature")),
            vital_weight=self.parse_float(vitals.get("weight") or data.get("vital_weight")),
            vital_height=self.parse_float(vitals.get("height") or data.get("vital_height")),
            vital_bmi=self.parse_float(vitals.get("bmi") or data.get("vital_bmi")),
            vital_oxygen_saturation=self.parse_float(vitals.get("oxygen_saturation") or data.get("vital_oxygen_saturation")),
            status=self.normalize_status(data.get("status"), self.VALID_STATUSES) or "completed",
            source_system=data.get("source_system"),
            source_id=data.get("source_id"),
        )
        
        self.db.add(encounter)
        await self.db.flush()
        
        return encounter
    
    def _normalize_encounter_type(self, encounter_type: str) -> str:
        """Normalize encounter type to valid values."""
        type_lower = encounter_type.lower().strip().replace(" ", "_")
        
        # Common aliases
        aliases = {
            "visit": "office_visit",
            "office": "office_visit",
            "er": "emergency",
            "ed": "emergency",
            "emergency_room": "emergency",
            "virtual": "telehealth",
            "video": "telehealth",
            "phone": "telehealth",
            "hospital": "inpatient",
            "admission": "inpatient",
            "clinic": "outpatient",
            "urgent": "urgent_care",
            "home": "home_visit",
            "labs": "lab_visit",
            "xray": "imaging",
            "mri": "imaging",
            "ct": "imaging",
            "surgery": "procedure",
            "followup": "follow_up",
        }
        
        if type_lower in aliases:
            return aliases[type_lower]
        
        if type_lower in self.VALID_ENCOUNTER_TYPES:
            return type_lower
        
        return "office_visit"  # Default
    
    def _build_clinical_notes(self, data: dict) -> Optional[str]:
        """Build clinical notes from SOAP components."""
        parts = []
        
        if data.get("chief_complaint"):
            parts.append(f"Chief Complaint: {data['chief_complaint']}")
        
        if data.get("subjective"):
            parts.append(f"\nSubjective:\n{data['subjective']}")
        
        if data.get("objective"):
            parts.append(f"\nObjective:\n{data['objective']}")
        
        if data.get("assessment"):
            parts.append(f"\nAssessment:\n{data['assessment']}")
        
        if data.get("plan"):
            parts.append(f"\nPlan:\n{data['plan']}")
        
        return "\n".join(parts) if parts else None
    
    def _parse_int(self, value) -> Optional[int]:
        """Parse integer from various formats."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return None
        return None
    
    async def ingest_soap_note(
        self,
        patient_id: int,
        encounter_date: datetime,
        subjective: str,
        objective: str,
        assessment: str,
        plan: str,
        provider_name: Optional[str] = None,
        **kwargs,
    ) -> Encounter:
        """Convenience method for ingesting SOAP format notes.
        
        Args:
            patient_id: Patient ID
            encounter_date: Date/time of the encounter
            subjective: Patient's reported symptoms/history
            objective: Physical exam findings, vitals
            assessment: Provider's assessment/diagnoses
            plan: Treatment plan
            provider_name: Name of the provider
            **kwargs: Additional encounter fields
            
        Returns:
            Created Encounter instance
        """
        data = {
            "patient_id": patient_id,
            "encounter_date": encounter_date,
            "subjective": subjective,
            "objective": objective,
            "assessment": assessment,
            "plan": plan,
            "provider_name": provider_name,
            **kwargs,
        }
        
        return await self.ingest_single(data)
    
    async def add_diagnosis(
        self,
        encounter_id: int,
        diagnosis_code: str,
        diagnosis_description: str,
    ) -> Encounter:
        """Add a diagnosis to an existing encounter.
        
        Args:
            encounter_id: ID of the encounter
            diagnosis_code: ICD-10 or other diagnosis code
            diagnosis_description: Human-readable description
            
        Returns:
            Updated Encounter instance
        """
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Encounter).where(Encounter.id == encounter_id)
        )
        encounter = result.scalar_one_or_none()
        
        if not encounter:
            raise ValueError(f"Encounter {encounter_id} not found")
        
        # Parse existing diagnoses
        existing = []
        if encounter.diagnoses:
            try:
                existing = json.loads(encounter.diagnoses)
            except json.JSONDecodeError:
                existing = [encounter.diagnoses]
        
        # Add new diagnosis
        new_diagnosis = f"{diagnosis_code} - {diagnosis_description}"
        if new_diagnosis not in existing:
            existing.append(new_diagnosis)
            encounter.diagnoses = json.dumps(existing)
        
        await self.db.flush()
        return encounter
