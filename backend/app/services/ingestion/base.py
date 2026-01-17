"""Base ingestion service with common functionality."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Patient

T = TypeVar("T")


class IngestionResult:
    """Result of an ingestion operation."""
    
    def __init__(
        self,
        success: bool,
        records_created: int = 0,
        records_updated: int = 0,
        records_skipped: int = 0,
        errors: list[str] | None = None,
    ):
        self.success = success
        self.records_created = records_created
        self.records_updated = records_updated
        self.records_skipped = records_skipped
        self.errors = errors or []
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }


class IngestionService(ABC, Generic[T]):
    """Base class for data ingestion services.
    
    Provides common functionality for ingesting medical data
    from various sources (JSON, CSV, FHIR, etc.).
    """
    
    def __init__(self, db: AsyncSession, user_id: int | None = None):
        self.db = db
        self.user_id = user_id
    
    async def get_or_create_patient(
        self,
        patient_id: Optional[int] = None,
        external_id: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Patient:
        """Get existing patient or create a new one.
        
        Args:
            patient_id: Internal patient ID
            external_id: External system patient ID
            first_name: Patient's first name (for creation)
            last_name: Patient's last name (for creation)
            
        Returns:
            Patient model instance
            
        Raises:
            ValueError: If patient cannot be found or created
        """
        # Try to find by internal ID first
        if patient_id:
            query = select(Patient).where(Patient.id == patient_id)
            if self.user_id is not None:
                query = query.where(Patient.user_id == self.user_id)
            result = await self.db.execute(query)
            patient = result.scalar_one_or_none()
            if patient:
                return patient
        
        # Try to find by external ID
        if external_id:
            query = select(Patient).where(Patient.external_id == external_id)
            if self.user_id is not None:
                query = query.where(Patient.user_id == self.user_id)
            result = await self.db.execute(query)
            patient = result.scalar_one_or_none()
            if patient:
                return patient
            
            # Create new patient with external ID
            if first_name and last_name:
                if self.user_id is None:
                    raise ValueError("Cannot create patient without an owning user.")
                patient = Patient(
                    external_id=external_id,
                    user_id=self.user_id,
                    first_name=first_name,
                    last_name=last_name,
                )
                self.db.add(patient)
                await self.db.flush()
                return patient
        
        raise ValueError(
            "Cannot find or create patient. Provide patient_id, "
            "external_id, or external_id with first_name and last_name."
        )
    
    def parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Try common formats
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%m/%d/%Y %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None
    
    def parse_float(self, value: Any) -> Optional[float]:
        """Parse float from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Remove common non-numeric characters
                cleaned = value.replace(",", "").replace(" ", "")
                return float(cleaned)
            except ValueError:
                return None
        return None
    
    def normalize_status(self, status: Optional[str], valid_values: list[str]) -> Optional[str]:
        """Normalize status value to valid options."""
        if status is None:
            return None
        status_lower = status.lower().strip()
        for valid in valid_values:
            if status_lower == valid.lower():
                return valid
        return None
    
    @abstractmethod
    async def ingest_single(self, data: dict) -> T:
        """Ingest a single record.
        
        Args:
            data: Dictionary containing record data
            
        Returns:
            Created model instance
        """
        pass
    
    async def ingest_batch(self, records: list[dict]) -> IngestionResult:
        """Ingest multiple records in a batch.
        
        Args:
            records: List of dictionaries containing record data
            
        Returns:
            IngestionResult with statistics
        """
        created = 0
        skipped = 0
        errors = []
        
        for i, record in enumerate(records):
            try:
                await self.ingest_single(record)
                created += 1
            except Exception as e:
                errors.append(f"Record {i}: {str(e)}")
                skipped += 1
        
        return IngestionResult(
            success=len(errors) == 0,
            records_created=created,
            records_skipped=skipped,
            errors=errors,
        )
