from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class InsightsLabItem(BaseModel):
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    collected_at: Optional[datetime] = None
    is_abnormal: bool = False


class InsightsMedicationItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    status: Optional[str] = None
    prescribed_at: Optional[datetime] = None
    start_date: Optional[date] = None


class PatientInsightsResponse(BaseModel):
    patient_id: int
    lab_total: int
    lab_abnormal: int
    recent_labs: list[InsightsLabItem]
    active_medications: int
    recent_medications: list[InsightsMedicationItem]
    a1c_series: list[float]
