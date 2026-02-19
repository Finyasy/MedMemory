"""Profile management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_authenticated_user
from app.database import get_db
from app.models import (
    EmergencyContact,
    FamilyHistory,
    GrowthMeasurement,
    Patient,
    PatientAllergy,
    PatientCondition,
    PatientEmergencyInfo,
    PatientInsurance,
    PatientLifestyle,
    PatientProvider,
    PatientVaccination,
    User,
)
from app.schemas.profile import (
    AllergyCreate,
    AllergyResponse,
    AllergyUpdate,
    BasicProfileUpdate,
    ConditionCreate,
    ConditionResponse,
    ConditionUpdate,
    EmergencyContactCreate,
    EmergencyContactResponse,
    EmergencyContactUpdate,
    EmergencyInfoResponse,
    EmergencyInfoUpdate,
    FamilyHistoryCreate,
    FamilyHistoryResponse,
    FullProfileResponse,
    GrowthMeasurementCreate,
    GrowthMeasurementResponse,
    InsuranceCreate,
    InsuranceResponse,
    LifestyleResponse,
    LifestyleUpdate,
    ProfileCompletionStatus,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
    VaccinationCreate,
    VaccinationResponse,
)

router = APIRouter(prefix="/profile", tags=["Profile"])
logger = logging.getLogger(__name__)


async def get_primary_patient(
    db: AsyncSession,
    user_id: int,
    *query_options,
) -> Patient:
    """Return a deterministic primary patient row for a user.

    Some local/dev datasets can contain more than one non-dependent patient row
    for the same user. In that case, pick the oldest row and continue instead of
    throwing an unhandled MultipleResultsFound error.
    """
    query = (
        select(Patient)
        .where(
            Patient.user_id == user_id,
            Patient.is_dependent.is_(False),
        )
        .order_by(Patient.created_at.asc(), Patient.id.asc())
        .limit(2)
    )
    if query_options:
        query = query.options(*query_options)
    result = await db.execute(query)
    matches = result.scalars().all()
    if not matches:
        raise HTTPException(status_code=404, detail="No primary patient profile found")
    if len(matches) > 1:
        logger.warning(
            "Multiple primary patient rows found for user_id=%s, selecting patient_id=%s",
            user_id,
            matches[0].id,
        )
    return matches[0]


async def get_user_patient(
    db: AsyncSession, user: User, patient_id: int | None = None
) -> Patient:
    """Get the patient for the current user or specified patient ID."""
    if patient_id:
        result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient

    return await get_primary_patient(db, user.id)


def calculate_profile_completion(patient: Patient) -> ProfileCompletionStatus:
    """Calculate profile completion percentage."""
    sections = {}
    total_weight = 0
    completed_weight = 0

    # Basic info (weight: 25)
    basic_fields = [
        patient.date_of_birth,
        patient.sex,
        patient.blood_type,
        patient.height_cm,
        patient.weight_kg,
    ]
    basic_filled = sum(1 for f in basic_fields if f is not None)
    basic_pct = int((basic_filled / len(basic_fields)) * 100)
    sections["basic_info"] = {"complete": basic_pct == 100, "percentage": basic_pct}
    total_weight += 25
    completed_weight += 25 * (basic_pct / 100)

    # Emergency (weight: 20)
    emergency_score = 0
    if patient.emergency_info:
        emergency_score += 50
    if patient.emergency_contacts:
        emergency_score += 50
    sections["emergency"] = {
        "complete": emergency_score == 100,
        "percentage": emergency_score,
    }
    total_weight += 20
    completed_weight += 20 * (emergency_score / 100)

    # Medical history (weight: 25)
    medical_score = 0
    if patient.allergies_list:
        medical_score += 33
    if patient.conditions_list:
        medical_score += 33
    if patient.family_history_list:
        medical_score += 34
    sections["medical_history"] = {
        "complete": medical_score >= 99,
        "percentage": min(medical_score, 100),
    }
    total_weight += 25
    completed_weight += 25 * (medical_score / 100)

    # Providers (weight: 15)
    providers_score = 100 if patient.providers else 0
    sections["providers"] = {
        "complete": providers_score == 100,
        "percentage": providers_score,
    }
    total_weight += 15
    completed_weight += 15 * (providers_score / 100)

    # Lifestyle (weight: 15)
    lifestyle_score = 0
    if patient.lifestyle:
        lf = patient.lifestyle
        lifestyle_fields = [
            lf.smoking_status,
            lf.alcohol_use,
            lf.exercise_frequency,
            lf.sleep_hours,
        ]
        lifestyle_filled = sum(1 for f in lifestyle_fields if f is not None)
        lifestyle_score = int((lifestyle_filled / len(lifestyle_fields)) * 100)
    sections["lifestyle"] = {
        "complete": lifestyle_score == 100,
        "percentage": lifestyle_score,
    }
    total_weight += 15
    completed_weight += 15 * (lifestyle_score / 100)

    overall = int((completed_weight / total_weight) * 100) if total_weight > 0 else 0

    return ProfileCompletionStatus(overall_percentage=overall, sections=sections)


@router.get("", response_model=FullProfileResponse)
async def get_profile(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get complete profile for current user or specified patient."""
    query_options = (
        selectinload(Patient.emergency_info),
        selectinload(Patient.emergency_contacts),
        selectinload(Patient.allergies_list),
        selectinload(Patient.conditions_list),
        selectinload(Patient.providers),
        selectinload(Patient.lifestyle),
        selectinload(Patient.insurance_list),
        selectinload(Patient.family_history_list),
        selectinload(Patient.vaccinations),
        selectinload(Patient.growth_measurements),
    )

    if patient_id is not None:
        result = await db.execute(
            select(Patient)
            .options(*query_options)
            .where(
                Patient.user_id == current_user.id,
                Patient.id == patient_id,
            )
        )
        patient = result.scalar_one_or_none()
    else:
        patient = await get_primary_patient(db, current_user.id, *query_options)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    completion = calculate_profile_completion(patient)

    return FullProfileResponse(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        age=patient.age,
        sex=patient.sex,
        gender=patient.gender,
        blood_type=patient.blood_type,
        height_cm=patient.height_cm,
        weight_kg=patient.weight_kg,
        phone=patient.phone,
        email=patient.email,
        address=patient.address,
        preferred_language=patient.preferred_language,
        timezone=patient.timezone,
        profile_photo_url=patient.profile_photo_url,
        is_dependent=patient.is_dependent,
        profile_completed_at=patient.profile_completed_at,
        emergency_info=patient.emergency_info,
        emergency_contacts=[
            EmergencyContactResponse(
                id=c.id,
                patient_id=c.patient_id,
                name=c.name,
                relationship=c.contact_relationship,
                phone=c.phone,
                email=c.email,
                is_primary=c.is_primary,
            )
            for c in patient.emergency_contacts
        ],
        allergies=patient.allergies_list,
        conditions=patient.conditions_list,
        providers=patient.providers,
        lifestyle=patient.lifestyle,
        insurance=patient.insurance_list,
        family_history=patient.family_history_list,
        vaccinations=patient.vaccinations,
        growth_measurements=patient.growth_measurements,
        profile_completion=completion,
    )


@router.put("/basic", response_model=FullProfileResponse)
async def update_basic_profile(
    data: BasicProfileUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update basic profile information."""
    patient = await get_user_patient(db, current_user, patient_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)

    await db.flush()
    await db.refresh(patient)

    return await get_profile(patient_id=patient.id, db=db, current_user=current_user)


# === Emergency Info ===


@router.put("/emergency", response_model=EmergencyInfoResponse)
async def update_emergency_info(
    data: EmergencyInfoUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update emergency information."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientEmergencyInfo).where(
            PatientEmergencyInfo.patient_id == patient.id
        )
    )
    info = result.scalar_one_or_none()

    if not info:
        info = PatientEmergencyInfo(
            patient_id=patient.id, **data.model_dump(exclude_unset=True)
        )
        db.add(info)
    else:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(info, field, value)

    await db.flush()
    await db.refresh(info)
    return info


# === Emergency Contacts ===


@router.get("/emergency-contacts", response_model=list[EmergencyContactResponse])
async def list_emergency_contacts(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List emergency contacts."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(EmergencyContact)
        .where(EmergencyContact.patient_id == patient.id)
        .order_by(EmergencyContact.priority_order)
    )
    contacts = result.scalars().all()
    return [
        EmergencyContactResponse(
            id=c.id,
            patient_id=c.patient_id,
            name=c.name,
            relationship=c.contact_relationship,
            phone=c.phone,
            email=c.email,
            is_primary=c.is_primary,
        )
        for c in contacts
    ]


@router.post(
    "/emergency-contacts", response_model=EmergencyContactResponse, status_code=201
)
async def create_emergency_contact(
    data: EmergencyContactCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add an emergency contact."""
    patient = await get_user_patient(db, current_user, patient_id)

    contact_data = data.model_dump()
    contact_data["contact_relationship"] = contact_data.pop("relationship")
    contact = EmergencyContact(patient_id=patient.id, **contact_data)
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return EmergencyContactResponse(
        id=contact.id,
        patient_id=contact.patient_id,
        name=contact.name,
        relationship=contact.contact_relationship,
        phone=contact.phone,
        email=contact.email,
        is_primary=contact.is_primary,
    )


@router.put("/emergency-contacts/{contact_id}", response_model=EmergencyContactResponse)
async def update_emergency_contact(
    contact_id: int,
    data: EmergencyContactUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update an emergency contact."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id, EmergencyContact.patient_id == patient.id
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = data.model_dump(exclude_unset=True)
    if "relationship" in update_data:
        update_data["contact_relationship"] = update_data.pop("relationship")
    for field, value in update_data.items():
        setattr(contact, field, value)

    await db.flush()
    await db.refresh(contact)
    return EmergencyContactResponse(
        id=contact.id,
        patient_id=contact.patient_id,
        name=contact.name,
        relationship=contact.contact_relationship,
        phone=contact.phone,
        email=contact.email,
        is_primary=contact.is_primary,
    )


@router.delete("/emergency-contacts/{contact_id}", status_code=204)
async def delete_emergency_contact(
    contact_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete an emergency contact."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id, EmergencyContact.patient_id == patient.id
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)


# === Allergies ===


@router.get("/allergies", response_model=list[AllergyResponse])
async def list_allergies(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List allergies."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientAllergy).where(PatientAllergy.patient_id == patient.id)
    )
    return result.scalars().all()


@router.post("/allergies", response_model=AllergyResponse, status_code=201)
async def create_allergy(
    data: AllergyCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add an allergy."""
    patient = await get_user_patient(db, current_user, patient_id)
    allergy = PatientAllergy(patient_id=patient.id, **data.model_dump())
    db.add(allergy)
    await db.flush()
    await db.refresh(allergy)
    return allergy


@router.put("/allergies/{allergy_id}", response_model=AllergyResponse)
async def update_allergy(
    allergy_id: int,
    data: AllergyUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update an allergy."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientAllergy).where(
            PatientAllergy.id == allergy_id, PatientAllergy.patient_id == patient.id
        )
    )
    allergy = result.scalar_one_or_none()
    if not allergy:
        raise HTTPException(status_code=404, detail="Allergy not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(allergy, field, value)

    await db.flush()
    await db.refresh(allergy)
    return allergy


@router.delete("/allergies/{allergy_id}", status_code=204)
async def delete_allergy(
    allergy_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete an allergy."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientAllergy).where(
            PatientAllergy.id == allergy_id, PatientAllergy.patient_id == patient.id
        )
    )
    allergy = result.scalar_one_or_none()
    if not allergy:
        raise HTTPException(status_code=404, detail="Allergy not found")

    db.delete(allergy)


# === Conditions ===


@router.get("/conditions", response_model=list[ConditionResponse])
async def list_conditions(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List conditions."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientCondition).where(PatientCondition.patient_id == patient.id)
    )
    return result.scalars().all()


@router.post("/conditions", response_model=ConditionResponse, status_code=201)
async def create_condition(
    data: ConditionCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add a condition."""
    patient = await get_user_patient(db, current_user, patient_id)
    condition = PatientCondition(patient_id=patient.id, **data.model_dump())
    db.add(condition)
    await db.flush()
    await db.refresh(condition)
    return condition


@router.put("/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition(
    condition_id: int,
    data: ConditionUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update a condition."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientCondition).where(
            PatientCondition.id == condition_id,
            PatientCondition.patient_id == patient.id,
        )
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(condition, field, value)

    await db.flush()
    await db.refresh(condition)
    return condition


@router.delete("/conditions/{condition_id}", status_code=204)
async def delete_condition(
    condition_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a condition."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientCondition).where(
            PatientCondition.id == condition_id,
            PatientCondition.patient_id == patient.id,
        )
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")

    db.delete(condition)


# === Providers ===


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List healthcare providers."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientProvider).where(PatientProvider.patient_id == patient.id)
    )
    return result.scalars().all()


@router.post("/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(
    data: ProviderCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add a healthcare provider."""
    patient = await get_user_patient(db, current_user, patient_id)
    provider = PatientProvider(patient_id=patient.id, **data.model_dump())
    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    return provider


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update a healthcare provider."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientProvider).where(
            PatientProvider.id == provider_id, PatientProvider.patient_id == patient.id
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)

    await db.flush()
    await db.refresh(provider)
    return provider


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a healthcare provider."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientProvider).where(
            PatientProvider.id == provider_id, PatientProvider.patient_id == patient.id
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    db.delete(provider)


# === Lifestyle ===


@router.get("/lifestyle", response_model=LifestyleResponse | None)
async def get_lifestyle(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get lifestyle information."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientLifestyle).where(PatientLifestyle.patient_id == patient.id)
    )
    return result.scalar_one_or_none()


@router.put("/lifestyle", response_model=LifestyleResponse)
async def update_lifestyle(
    data: LifestyleUpdate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update lifestyle information."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientLifestyle).where(PatientLifestyle.patient_id == patient.id)
    )
    lifestyle = result.scalar_one_or_none()

    if not lifestyle:
        lifestyle = PatientLifestyle(
            patient_id=patient.id, **data.model_dump(exclude_unset=True)
        )
        db.add(lifestyle)
    else:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(lifestyle, field, value)

    await db.flush()
    await db.refresh(lifestyle)
    return lifestyle


# === Insurance ===


@router.get("/insurance", response_model=list[InsuranceResponse])
async def list_insurance(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List insurance information."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientInsurance).where(PatientInsurance.patient_id == patient.id)
    )
    return result.scalars().all()


@router.post("/insurance", response_model=InsuranceResponse, status_code=201)
async def create_insurance(
    data: InsuranceCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add insurance information."""
    patient = await get_user_patient(db, current_user, patient_id)
    insurance = PatientInsurance(patient_id=patient.id, **data.model_dump())
    db.add(insurance)
    await db.flush()
    await db.refresh(insurance)
    return insurance


@router.delete("/insurance/{insurance_id}", status_code=204)
async def delete_insurance(
    insurance_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete insurance information."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientInsurance).where(
            PatientInsurance.id == insurance_id,
            PatientInsurance.patient_id == patient.id,
        )
    )
    insurance = result.scalar_one_or_none()
    if not insurance:
        raise HTTPException(status_code=404, detail="Insurance not found")

    db.delete(insurance)


# === Family History ===


@router.get("/family-history", response_model=list[FamilyHistoryResponse])
async def list_family_history(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List family medical history."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(FamilyHistory).where(FamilyHistory.patient_id == patient.id)
    )
    return result.scalars().all()


@router.post("/family-history", response_model=FamilyHistoryResponse, status_code=201)
async def create_family_history(
    data: FamilyHistoryCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add family history entry."""
    patient = await get_user_patient(db, current_user, patient_id)
    history = FamilyHistory(patient_id=patient.id, **data.model_dump())
    db.add(history)
    await db.flush()
    await db.refresh(history)
    return history


@router.delete("/family-history/{history_id}", status_code=204)
async def delete_family_history(
    history_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete family history entry."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(FamilyHistory).where(
            FamilyHistory.id == history_id, FamilyHistory.patient_id == patient.id
        )
    )
    history = result.scalar_one_or_none()
    if not history:
        raise HTTPException(status_code=404, detail="Family history entry not found")

    db.delete(history)


# === Vaccinations ===


@router.get("/vaccinations", response_model=list[VaccinationResponse])
async def list_vaccinations(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List vaccinations."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(PatientVaccination)
        .where(PatientVaccination.patient_id == patient.id)
        .order_by(PatientVaccination.date_administered.desc())
    )
    return result.scalars().all()


@router.post("/vaccinations", response_model=VaccinationResponse, status_code=201)
async def create_vaccination(
    data: VaccinationCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add a vaccination record."""
    patient = await get_user_patient(db, current_user, patient_id)
    vaccination = PatientVaccination(patient_id=patient.id, **data.model_dump())
    db.add(vaccination)
    await db.flush()
    await db.refresh(vaccination)
    return vaccination


@router.delete("/vaccinations/{vaccination_id}", status_code=204)
async def delete_vaccination(
    vaccination_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a vaccination record."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(PatientVaccination).where(
            PatientVaccination.id == vaccination_id,
            PatientVaccination.patient_id == patient.id,
        )
    )
    vaccination = result.scalar_one_or_none()
    if not vaccination:
        raise HTTPException(status_code=404, detail="Vaccination not found")

    db.delete(vaccination)


# === Growth Measurements ===


@router.get("/growth", response_model=list[GrowthMeasurementResponse])
async def list_growth_measurements(
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List growth measurements."""
    patient = await get_user_patient(db, current_user, patient_id)
    result = await db.execute(
        select(GrowthMeasurement)
        .where(GrowthMeasurement.patient_id == patient.id)
        .order_by(GrowthMeasurement.measurement_date.desc())
    )
    return result.scalars().all()


@router.post("/growth", response_model=GrowthMeasurementResponse, status_code=201)
async def create_growth_measurement(
    data: GrowthMeasurementCreate,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add a growth measurement."""
    patient = await get_user_patient(db, current_user, patient_id)
    measurement = GrowthMeasurement(patient_id=patient.id, **data.model_dump())
    db.add(measurement)
    await db.flush()
    await db.refresh(measurement)
    return measurement


@router.delete("/growth/{measurement_id}", status_code=204)
async def delete_growth_measurement(
    measurement_id: int,
    patient_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a growth measurement."""
    patient = await get_user_patient(db, current_user, patient_id)

    result = await db.execute(
        select(GrowthMeasurement).where(
            GrowthMeasurement.id == measurement_id,
            GrowthMeasurement.patient_id == patient.id,
        )
    )
    measurement = result.scalar_one_or_none()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")

    db.delete(measurement)
