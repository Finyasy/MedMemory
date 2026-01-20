"""Insights API for dashboards."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.models import LabResult, Medication, User
from app.schemas.insights import (
    InsightsLabItem,
    InsightsMedicationItem,
    PatientInsightsResponse,
)

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/patient/{patient_id}", response_model=PatientInsightsResponse)
async def get_patient_insights(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return lightweight lab/medication insights for dashboards."""
    await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)

    lab_total = await db.scalar(
        select(func.count()).select_from(LabResult).where(LabResult.patient_id == patient_id)
    )
    lab_abnormal = await db.scalar(
        select(func.count()).select_from(LabResult).where(
            LabResult.patient_id == patient_id,
            LabResult.is_abnormal == True,
        )
    )

    recent_lab_rows = await db.execute(
        select(LabResult)
        .where(LabResult.patient_id == patient_id)
        .order_by(LabResult.collected_at.desc().nullslast(), LabResult.id.desc())
        .limit(50)
    )
    recent_labs_raw = recent_lab_rows.scalars().all()
    seen_tests: set[str] = set()
    recent_labs: list[InsightsLabItem] = []
    for lab in recent_labs_raw:
        if lab.test_name in seen_tests:
            continue
        seen_tests.add(lab.test_name)
        recent_labs.append(
            InsightsLabItem(
                test_name=lab.test_name,
                value=lab.value or (str(lab.numeric_value) if lab.numeric_value is not None else None),
                unit=lab.unit,
                collected_at=lab.collected_at,
                is_abnormal=lab.is_abnormal,
            )
        )
        if len(recent_labs) >= 4:
            break

    meds_rows = await db.execute(
        select(Medication)
        .where(Medication.patient_id == patient_id, Medication.is_active == True)
        .order_by(Medication.prescribed_at.desc().nullslast(), Medication.id.desc())
        .limit(5)
    )
    meds = meds_rows.scalars().all()
    active_medications = len(meds)
    recent_medications = [
        InsightsMedicationItem(
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            status=med.status or ("active" if med.is_active else None),
            prescribed_at=med.prescribed_at,
            start_date=med.start_date,
        )
        for med in meds
    ]

    a1c_rows = await db.execute(
        select(LabResult)
        .where(
            LabResult.patient_id == patient_id,
            LabResult.test_name.ilike("%a1c%"),
        )
        .order_by(LabResult.collected_at.desc().nullslast(), LabResult.id.desc())
        .limit(6)
    )
    a1c_series: list[float] = []
    for lab in a1c_rows.scalars().all():
        if lab.numeric_value is not None:
            a1c_series.append(lab.numeric_value)
        elif lab.value:
            try:
                a1c_series.append(float(lab.value))
            except ValueError:
                continue
    a1c_series.reverse()

    return PatientInsightsResponse(
        patient_id=patient_id,
        lab_total=lab_total or 0,
        lab_abnormal=lab_abnormal or 0,
        recent_labs=recent_labs,
        active_medications=active_medications,
        recent_medications=recent_medications,
        a1c_series=a1c_series,
    )
