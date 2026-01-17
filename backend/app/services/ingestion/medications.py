"""Medications ingestion service."""

from datetime import date
from typing import Optional

from app.models import Medication
from app.services.ingestion.base import IngestionService


class MedicationIngestionService(IngestionService[Medication]):
    """Service for ingesting medication/prescription data.
    
    Supports various medication data formats and normalizes them
    to the Medication model schema.
    
    Example input format:
    {
        "patient_id": 1,
        "name": "Lisinopril",
        "generic_name": "Lisinopril",
        "drug_code": "314076",  # RxNorm code
        "drug_class": "ACE Inhibitor",
        "dosage": "10mg",
        "dosage_value": 10.0,
        "dosage_unit": "mg",
        "frequency": "once daily",
        "route": "oral",
        "start_date": "2024-01-01",
        "end_date": null,
        "is_active": true,
        "status": "active",
        "prescriber": "Dr. Johnson",
        "pharmacy": "CVS Pharmacy",
        "indication": "Hypertension",
        "instructions": "Take in the morning with water",
        "quantity": 30,
        "refills_remaining": 3
    }
    """
    
    VALID_STATUSES = ["active", "completed", "discontinued", "on-hold", "cancelled"]
    
    VALID_ROUTES = [
        "oral", "iv", "im", "subcutaneous", "topical", "inhalation",
        "ophthalmic", "otic", "nasal", "rectal", "transdermal", "sublingual"
    ]
    
    COMMON_DRUG_CLASSES = {
        "lisinopril": "ACE Inhibitor",
        "enalapril": "ACE Inhibitor",
        "metoprolol": "Beta Blocker",
        "atenolol": "Beta Blocker",
        "amlodipine": "Calcium Channel Blocker",
        "metformin": "Antidiabetic",
        "insulin": "Antidiabetic",
        "atorvastatin": "Statin",
        "simvastatin": "Statin",
        "omeprazole": "Proton Pump Inhibitor",
        "pantoprazole": "Proton Pump Inhibitor",
        "levothyroxine": "Thyroid Hormone",
        "amoxicillin": "Antibiotic",
        "azithromycin": "Antibiotic",
        "prednisone": "Corticosteroid",
        "ibuprofen": "NSAID",
        "aspirin": "NSAID",
        "acetaminophen": "Analgesic",
        "gabapentin": "Anticonvulsant",
        "sertraline": "SSRI",
        "fluoxetine": "SSRI",
        "alprazolam": "Benzodiazepine",
        "lorazepam": "Benzodiazepine",
        "warfarin": "Anticoagulant",
        "apixaban": "Anticoagulant",
    }
    
    async def ingest_single(self, data: dict) -> Medication:
        """Ingest a single medication record.
        
        Args:
            data: Dictionary containing medication data
            
        Returns:
            Created Medication model instance
        """
        # Get or validate patient
        patient = await self.get_or_create_patient(
            patient_id=data.get("patient_id"),
            external_id=data.get("patient_external_id"),
            first_name=data.get("patient_first_name"),
            last_name=data.get("patient_last_name"),
        )
        
        # Parse and validate medication name
        name = data.get("name", "").strip()
        if not name:
            raise ValueError("name is required")
        
        # Auto-detect drug class if not provided
        drug_class = data.get("drug_class")
        if not drug_class:
            drug_class = self._detect_drug_class(name)
        
        # Parse dosage components
        dosage_value, dosage_unit = self._parse_dosage(
            dosage=data.get("dosage"),
            dosage_value=data.get("dosage_value"),
            dosage_unit=data.get("dosage_unit"),
        )
        
        # Normalize route
        route = self._normalize_route(data.get("route"))
        
        # Parse status and active flag
        status = self.normalize_status(data.get("status"), self.VALID_STATUSES)
        is_active = data.get("is_active")
        if is_active is None:
            is_active = status in ["active", None]
        
        # Parse dates
        start_date = self._parse_date(data.get("start_date"))
        end_date = self._parse_date(data.get("end_date"))
        
        # Create medication record
        medication = Medication(
            patient_id=patient.id,
            name=name,
            generic_name=data.get("generic_name"),
            drug_code=data.get("drug_code"),
            drug_class=drug_class,
            dosage=data.get("dosage"),
            dosage_value=dosage_value,
            dosage_unit=dosage_unit,
            frequency=data.get("frequency"),
            route=route,
            start_date=start_date,
            end_date=end_date,
            prescribed_at=self.parse_datetime(data.get("prescribed_at")),
            is_active=is_active,
            status=status or "active",
            discontinue_reason=data.get("discontinue_reason"),
            prescriber=data.get("prescriber"),
            pharmacy=data.get("pharmacy"),
            quantity=data.get("quantity"),
            refills_remaining=data.get("refills_remaining"),
            indication=data.get("indication"),
            instructions=data.get("instructions"),
            notes=data.get("notes"),
            source_system=data.get("source_system"),
            source_id=data.get("source_id"),
        )
        
        self.db.add(medication)
        await self.db.flush()
        
        return medication
    
    def _detect_drug_class(self, name: str) -> Optional[str]:
        """Auto-detect drug class from medication name."""
        name_lower = name.lower()
        for drug, drug_class in self.COMMON_DRUG_CLASSES.items():
            if drug in name_lower:
                return drug_class
        return None
    
    def _parse_dosage(
        self,
        dosage: Optional[str],
        dosage_value: Optional[float],
        dosage_unit: Optional[str],
    ) -> tuple[Optional[float], Optional[str]]:
        """Parse dosage string into value and unit."""
        # If already provided separately
        if dosage_value is not None and dosage_unit is not None:
            return dosage_value, dosage_unit
        
        # Try to parse from dosage string
        if dosage:
            import re
            # Match patterns like "10mg", "500 mg", "2.5 mL"
            match = re.match(r"([\d.]+)\s*([a-zA-Z]+)", dosage.strip())
            if match:
                try:
                    value = float(match.group(1))
                    unit = match.group(2).lower()
                    return value, unit
                except ValueError:
                    pass
        
        return dosage_value, dosage_unit
    
    def _normalize_route(self, route: Optional[str]) -> Optional[str]:
        """Normalize administration route."""
        if not route:
            return None
        
        route_lower = route.lower().strip()
        
        # Common aliases
        aliases = {
            "po": "oral",
            "by mouth": "oral",
            "intravenous": "iv",
            "intramuscular": "im",
            "subq": "subcutaneous",
            "sq": "subcutaneous",
            "sc": "subcutaneous",
            "inhaled": "inhalation",
            "eye drops": "ophthalmic",
            "ear drops": "otic",
            "patch": "transdermal",
        }
        
        if route_lower in aliases:
            return aliases[route_lower]
        
        if route_lower in self.VALID_ROUTES:
            return route_lower
        
        return route  # Return original if can't normalize
    
    def _parse_date(self, value) -> Optional[date]:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        
        dt = self.parse_datetime(value)
        if dt:
            return dt.date()
        return None
    
    async def discontinue_medication(
        self,
        medication_id: int,
        reason: Optional[str] = None,
        end_date: Optional[date] = None,
    ) -> Medication:
        """Discontinue an active medication.
        
        Args:
            medication_id: ID of the medication to discontinue
            reason: Reason for discontinuation
            end_date: Date medication was stopped (defaults to today)
            
        Returns:
            Updated Medication instance
        """
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Medication).where(Medication.id == medication_id)
        )
        medication = result.scalar_one_or_none()
        
        if not medication:
            raise ValueError(f"Medication {medication_id} not found")
        
        medication.is_active = False
        medication.status = "discontinued"
        medication.discontinue_reason = reason
        medication.end_date = end_date or date.today()
        
        await self.db.flush()
        return medication
