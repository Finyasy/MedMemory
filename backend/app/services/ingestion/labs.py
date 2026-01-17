"""Lab results ingestion service."""

from datetime import datetime
from typing import Optional

from app.models import LabResult
from app.services.ingestion.base import IngestionService


class LabIngestionService(IngestionService[LabResult]):
    """Service for ingesting laboratory test results.
    
    Supports various lab data formats and normalizes them
    to the LabResult model schema.
    
    Example input format:
    {
        "patient_id": 1,
        "test_name": "Complete Blood Count",
        "test_code": "26604-4",  # LOINC code
        "category": "Hematology",
        "value": "14.2",
        "numeric_value": 14.2,
        "unit": "g/dL",
        "reference_range": "12.0-16.0",
        "status": "normal",
        "collected_at": "2024-01-15T08:30:00",
        "resulted_at": "2024-01-15T14:00:00",
        "ordering_provider": "Dr. Smith",
        "performing_lab": "Quest Diagnostics",
        "notes": "Fasting sample"
    }
    """
    
    VALID_STATUSES = ["normal", "abnormal", "critical", "pending"]
    
    COMMON_LAB_CATEGORIES = {
        "cbc": "Hematology",
        "bmp": "Chemistry",
        "cmp": "Chemistry",
        "lipid": "Chemistry",
        "thyroid": "Endocrinology",
        "liver": "Chemistry",
        "renal": "Chemistry",
        "urinalysis": "Urinalysis",
        "culture": "Microbiology",
        "hba1c": "Endocrinology",
        "glucose": "Chemistry",
        "hemoglobin": "Hematology",
        "platelet": "Hematology",
        "wbc": "Hematology",
        "rbc": "Hematology",
    }
    
    async def ingest_single(self, data: dict) -> LabResult:
        """Ingest a single lab result.
        
        Args:
            data: Dictionary containing lab result data
            
        Returns:
            Created LabResult model instance
        """
        # Get or validate patient
        patient = await self.get_or_create_patient(
            patient_id=data.get("patient_id"),
            external_id=data.get("patient_external_id"),
            first_name=data.get("patient_first_name"),
            last_name=data.get("patient_last_name"),
        )
        
        # Parse and validate data
        test_name = data.get("test_name", "").strip()
        if not test_name:
            raise ValueError("test_name is required")
        
        # Auto-detect category if not provided
        category = data.get("category")
        if not category:
            category = self._detect_category(test_name)
        
        # Parse numeric value
        numeric_value = self.parse_float(data.get("numeric_value"))
        if numeric_value is None and data.get("value"):
            numeric_value = self.parse_float(data.get("value"))
        
        # Determine abnormal status
        status = self.normalize_status(data.get("status"), self.VALID_STATUSES)
        is_abnormal = self._check_abnormal(
            status=status,
            numeric_value=numeric_value,
            reference_range=data.get("reference_range"),
        )
        
        # Create lab result
        lab_result = LabResult(
            patient_id=patient.id,
            test_name=test_name,
            test_code=data.get("test_code"),
            category=category,
            value=str(data.get("value", "")) if data.get("value") else None,
            numeric_value=numeric_value,
            unit=data.get("unit"),
            reference_range=data.get("reference_range"),
            status=status or ("abnormal" if is_abnormal else "normal"),
            is_abnormal=is_abnormal,
            collected_at=self.parse_datetime(data.get("collected_at")),
            resulted_at=self.parse_datetime(data.get("resulted_at")),
            notes=data.get("notes"),
            ordering_provider=data.get("ordering_provider"),
            performing_lab=data.get("performing_lab"),
            source_system=data.get("source_system"),
            source_id=data.get("source_id"),
        )
        
        self.db.add(lab_result)
        await self.db.flush()
        
        return lab_result
    
    def _detect_category(self, test_name: str) -> Optional[str]:
        """Auto-detect lab category from test name."""
        test_lower = test_name.lower()
        for keyword, category in self.COMMON_LAB_CATEGORIES.items():
            if keyword in test_lower:
                return category
        return "General"
    
    def _check_abnormal(
        self,
        status: Optional[str],
        numeric_value: Optional[float],
        reference_range: Optional[str],
    ) -> bool:
        """Determine if result is abnormal."""
        # If status explicitly says abnormal/critical
        if status in ["abnormal", "critical"]:
            return True
        
        # Try to parse reference range and compare
        if numeric_value is not None and reference_range:
            try:
                # Handle ranges like "12.0-16.0" or "< 100" or "> 50"
                range_str = reference_range.strip()
                
                if "-" in range_str and not range_str.startswith("-"):
                    parts = range_str.split("-")
                    if len(parts) == 2:
                        low = float(parts[0].strip())
                        high = float(parts[1].strip())
                        return numeric_value < low or numeric_value > high
                
                elif range_str.startswith("<"):
                    threshold = float(range_str[1:].strip())
                    return numeric_value >= threshold
                
                elif range_str.startswith(">"):
                    threshold = float(range_str[1:].strip())
                    return numeric_value <= threshold
                    
            except (ValueError, IndexError):
                pass
        
        return False
    
    async def ingest_panel(
        self,
        patient_id: int,
        panel_name: str,
        results: list[dict],
        collected_at: Optional[datetime] = None,
        ordering_provider: Optional[str] = None,
    ) -> list[LabResult]:
        """Ingest a complete lab panel (multiple related tests).
        
        Args:
            patient_id: Patient ID
            panel_name: Name of the panel (e.g., "Complete Blood Count")
            results: List of individual test results
            collected_at: When samples were collected
            ordering_provider: Provider who ordered the panel
            
        Returns:
            List of created LabResult instances
        """
        created_results = []
        
        for result in results:
            # Add common panel info to each result
            result["patient_id"] = patient_id
            result["category"] = result.get("category", panel_name)
            if collected_at:
                result["collected_at"] = collected_at
            if ordering_provider:
                result["ordering_provider"] = ordering_provider
            
            lab_result = await self.ingest_single(result)
            created_results.append(lab_result)
        
        return created_results
