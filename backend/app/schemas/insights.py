from datetime import date, datetime

from pydantic import BaseModel


class InsightsLabItem(BaseModel):
    test_name: str
    value: str | None = None
    unit: str | None = None
    collected_at: datetime | None = None
    is_abnormal: bool = False


class InsightsMedicationItem(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    status: str | None = None
    prescribed_at: datetime | None = None
    start_date: date | None = None


class PatientInsightsResponse(BaseModel):
    patient_id: int
    lab_total: int
    lab_abnormal: int
    recent_labs: list[InsightsLabItem]
    active_medications: int
    recent_medications: list[InsightsMedicationItem]
    a1c_series: list[float]
