from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException

from app.api import profile as profile_module
from app.models import (
    EmergencyContact,
    FamilyHistory,
    GrowthMeasurement,
    Patient,
    PatientAllergy,
    PatientCondition,
    PatientEmergencyInfo,
    PatientLifestyle,
    PatientProvider,
    PatientVaccination,
    User,
)
from app.schemas.profile import (
    AllergyCreate,
    AllergyUpdate,
    BasicProfileUpdate,
    ConditionCreate,
    ConditionUpdate,
    EmergencyContactCreate,
    EmergencyContactUpdate,
    EmergencyInfoUpdate,
    FamilyHistoryCreate,
    GrowthMeasurementCreate,
    InsuranceCreate,
    LifestyleUpdate,
    ProviderCreate,
    ProviderUpdate,
    VaccinationCreate,
)


class FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self._values)

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None


class FakeAsyncSession:
    def __init__(self, execute_results=None):
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.flush_count = 0
        self.refresh_count = 0
        self._next_id = 100

    async def execute(self, _query):
        if not self.execute_results:
            raise AssertionError("Unexpected execute() call")
        return self.execute_results.pop(0)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flush_count += 1

    async def refresh(self, _obj):
        self.refresh_count += 1


def make_user() -> User:
    return User(
        id=1,
        email="user@example.com",
        hashed_password="hashed",
        full_name="User Example",
        is_active=True,
    )


def make_patient() -> Patient:
    return Patient(
        id=7,
        user_id=1,
        first_name="Alice",
        last_name="Patient",
        date_of_birth=date(1990, 2, 2),
        sex="female",
        blood_type="O+",
        height_cm=165,
        weight_kg=60,
        preferred_language="en",
        is_dependent=False,
    )


async def _return_patient(*_args, **_kwargs):
    return make_patient()


@pytest.mark.anyio
async def test_profile_helpers_handle_missing_multiple_and_mobile_scope(monkeypatch):
    missing_session = FakeAsyncSession([FakeScalarResult([])])
    with pytest.raises(HTTPException, match="No primary patient profile found"):
        await profile_module.get_primary_patient(missing_session, user_id=1)

    first_patient = make_patient()
    second_patient = make_patient()
    second_patient.id = 9
    multi_session = FakeAsyncSession([FakeScalarResult([first_patient, second_patient])])
    selected = await profile_module.get_primary_patient(multi_session, user_id=1)
    assert selected.id == 7

    enforced_ids: list[int] = []
    monkeypatch.setattr(
        profile_module,
        "enforce_mobile_patient_scope",
        lambda user, patient_id: enforced_ids.append(patient_id),
    )
    mobile_user = make_user()
    setattr(mobile_user, "_mobile_patient_id", 7)
    mobile_session = FakeAsyncSession([FakeScalarResult([make_patient()])])

    patient = await profile_module.get_user_patient(mobile_session, mobile_user)

    assert patient.id == 7
    assert enforced_ids == [7]

    not_found_session = FakeAsyncSession([FakeScalarResult([])])
    with pytest.raises(HTTPException, match="Patient not found"):
        await profile_module.get_user_patient(
            not_found_session,
            make_user(),
            patient_id=999,
        )


@pytest.mark.anyio
async def test_profile_get_and_basic_update_paths(monkeypatch):
    patient = make_patient()
    now = datetime.now(UTC)
    patient.emergency_info = PatientEmergencyInfo(
        id=11,
        patient_id=patient.id,
        organ_donor=True,
    )
    patient.emergency_contacts = [
        EmergencyContact(
            id=1,
            patient_id=patient.id,
            name="Jane Doe",
            contact_relationship="spouse",
            phone="555-0101",
            is_primary=True,
        )
    ]
    patient.allergies_list = [
        PatientAllergy(
            id=12,
            patient_id=patient.id,
            allergen="Dust",
            allergy_type="environmental",
            severity="mild",
            created_at=now,
        )
    ]
    patient.conditions_list = [
        PatientCondition(
            id=13,
            patient_id=patient.id,
            condition_name="Asthma",
            status="active",
            created_at=now,
        )
    ]
    patient.providers = [
        PatientProvider(
            id=14,
            patient_id=patient.id,
            provider_type="pcp",
            name="Dr. Maina",
            is_primary=False,
        )
    ]
    patient.lifestyle = PatientLifestyle(
        id=15,
        patient_id=patient.id,
        smoking_status="never",
        alcohol_use="never",
        exercise_frequency="moderate",
        sleep_hours=8,
    )
    patient.insurance_list = []
    patient.family_history_list = [
        FamilyHistory(
            id=16,
            patient_id=patient.id,
            relation="mother",
            condition="Diabetes",
            is_deceased=False,
        )
    ]
    patient.vaccinations = [
        PatientVaccination(
            id=17,
            patient_id=patient.id,
            vaccine_name="Influenza",
            date_administered=date(2025, 10, 1),
        )
    ]
    patient.growth_measurements = [
        GrowthMeasurement(
            id=18,
            patient_id=patient.id,
            measurement_date=date(2025, 1, 1),
            age_months=12,
        )
    ]

    async def fake_get_primary_patient(*_args, **_kwargs):
        return patient

    monkeypatch.setattr(profile_module, "get_primary_patient", fake_get_primary_patient)
    response = await profile_module.get_profile(
        db=FakeAsyncSession(),
        current_user=make_user(),
    )

    assert response.id == patient.id
    assert response.full_name == "Alice Patient"
    assert response.profile_completion.overall_percentage > 0
    assert response.emergency_contacts[0].relationship == "spouse"

    patient_for_update = make_patient()

    async def fake_get_user_patient(*_args, **_kwargs):
        return patient_for_update

    async def fake_get_profile(*_args, **kwargs):
        return {
            "patient_id": kwargs["patient_id"],
            "first_name": patient_for_update.first_name,
        }

    monkeypatch.setattr(profile_module, "get_user_patient", fake_get_user_patient)
    monkeypatch.setattr(profile_module, "get_profile", fake_get_profile)
    update_session = FakeAsyncSession()

    updated = await profile_module.update_basic_profile(
        data=BasicProfileUpdate(first_name="Alicia", blood_type="A-"),
        db=update_session,
        current_user=make_user(),
    )

    assert updated == {"patient_id": 7, "first_name": "Alicia"}
    assert update_session.flush_count == 1
    assert update_session.refresh_count == 1


@pytest.mark.anyio
async def test_profile_emergency_contact_allergy_and_condition_endpoints(monkeypatch):
    monkeypatch.setattr(profile_module, "get_user_patient", _return_patient)
    user = make_user()

    emergency_session = FakeAsyncSession([FakeScalarResult([])])
    emergency_info = await profile_module.update_emergency_info(
        data=EmergencyInfoUpdate(medical_alert="Asthma", organ_donor=True),
        db=emergency_session,
        current_user=user,
    )
    assert emergency_info.medical_alert == "Asthma"
    assert emergency_session.added[0].patient_id == 7

    existing_info = PatientEmergencyInfo(patient_id=7, medical_alert="Old")
    update_emergency_session = FakeAsyncSession([FakeScalarResult([existing_info])])
    updated_info = await profile_module.update_emergency_info(
        data=EmergencyInfoUpdate(preferred_hospital="Aga Khan"),
        db=update_emergency_session,
        current_user=user,
    )
    assert updated_info.preferred_hospital == "Aga Khan"

    listed_contacts = await profile_module.list_emergency_contacts(
        db=FakeAsyncSession(
            [
                FakeScalarResult(
                    [
                        EmergencyContact(
                            id=3,
                            patient_id=7,
                            name="Jane Doe",
                            contact_relationship="spouse",
                            phone="555-0101",
                            is_primary=True,
                        )
                    ]
                )
            ]
        ),
        current_user=user,
    )
    assert listed_contacts[0].relationship == "spouse"

    create_contact_session = FakeAsyncSession()
    created_contact = await profile_module.create_emergency_contact(
        data=EmergencyContactCreate(
            name="John Doe",
            relationship="parent",
            phone="555-0202",
            is_primary=False,
        ),
        db=create_contact_session,
        current_user=user,
    )
    assert created_contact.relationship == "parent"

    existing_contact = EmergencyContact(
        id=4,
        patient_id=7,
        name="John Doe",
        contact_relationship="parent",
        phone="555-0202",
        is_primary=False,
    )
    contact_session = FakeAsyncSession([FakeScalarResult([existing_contact])])
    updated_contact = await profile_module.update_emergency_contact(
        contact_id=4,
        data=EmergencyContactUpdate(relationship="guardian", is_primary=True),
        db=contact_session,
        current_user=user,
    )
    assert updated_contact.relationship == "guardian"
    assert updated_contact.is_primary is True
    await profile_module.delete_emergency_contact(
        contact_id=4,
        db=FakeAsyncSession([FakeScalarResult([existing_contact])]),
        current_user=user,
    )

    allergy = await profile_module.create_allergy(
        data=AllergyCreate(allergen="Peanuts", allergy_type="food", severity="severe"),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert allergy.allergen == "Peanuts"

    listed_allergies = await profile_module.list_allergies(
        db=FakeAsyncSession([FakeScalarResult([allergy])]),
        current_user=user,
    )
    assert listed_allergies[0].allergen == "Peanuts"

    allergy_session = FakeAsyncSession([FakeScalarResult([allergy])])
    updated_allergy = await profile_module.update_allergy(
        allergy_id=allergy.id,
        data=AllergyUpdate(reaction="Hives"),
        db=allergy_session,
        current_user=user,
    )
    assert updated_allergy.reaction == "Hives"
    await profile_module.delete_allergy(
        allergy_id=allergy.id,
        db=FakeAsyncSession([FakeScalarResult([allergy])]),
        current_user=user,
    )

    condition = await profile_module.create_condition(
        data=ConditionCreate(condition_name="Hypertension", status="active"),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert condition.condition_name == "Hypertension"
    listed_conditions = await profile_module.list_conditions(
        db=FakeAsyncSession([FakeScalarResult([condition])]),
        current_user=user,
    )
    assert listed_conditions[0].condition_name == "Hypertension"
    condition_session = FakeAsyncSession([FakeScalarResult([condition])])
    updated_condition = await profile_module.update_condition(
        condition_id=condition.id,
        data=ConditionUpdate(status="resolved"),
        db=condition_session,
        current_user=user,
    )
    assert updated_condition.status == "resolved"
    await profile_module.delete_condition(
        condition_id=condition.id,
        db=FakeAsyncSession([FakeScalarResult([condition])]),
        current_user=user,
    )


@pytest.mark.anyio
async def test_profile_provider_lifestyle_and_remaining_collections(monkeypatch):
    monkeypatch.setattr(profile_module, "get_user_patient", _return_patient)
    user = make_user()

    provider = await profile_module.create_provider(
        data=ProviderCreate(provider_type="pcp", name="Dr. Maina"),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert provider.name == "Dr. Maina"
    listed_providers = await profile_module.list_providers(
        db=FakeAsyncSession([FakeScalarResult([provider])]),
        current_user=user,
    )
    assert listed_providers[0].name == "Dr. Maina"
    provider_session = FakeAsyncSession([FakeScalarResult([provider])])
    updated_provider = await profile_module.update_provider(
        provider_id=provider.id,
        data=ProviderUpdate(is_primary=True, notes="Quarterly follow-up"),
        db=provider_session,
        current_user=user,
    )
    assert updated_provider.is_primary is True
    await profile_module.delete_provider(
        provider_id=provider.id,
        db=FakeAsyncSession([FakeScalarResult([provider])]),
        current_user=user,
    )

    assert (
        await profile_module.get_lifestyle(
            db=FakeAsyncSession([FakeScalarResult([])]),
            current_user=user,
        )
        is None
    )
    lifestyle = await profile_module.update_lifestyle(
        data=LifestyleUpdate(smoking_status="never", exercise_frequency="active"),
        db=FakeAsyncSession([FakeScalarResult([])]),
        current_user=user,
    )
    assert lifestyle.exercise_frequency == "active"
    existing_lifestyle = PatientLifestyle(patient_id=7, smoking_status="former")
    lifestyle_session = FakeAsyncSession([FakeScalarResult([existing_lifestyle])])
    updated_lifestyle = await profile_module.update_lifestyle(
        data=LifestyleUpdate(alcohol_use="occasional"),
        db=lifestyle_session,
        current_user=user,
    )
    assert updated_lifestyle.alcohol_use == "occasional"

    insurance = await profile_module.create_insurance(
        data=InsuranceCreate(provider_name="AAR", policy_number="POL-1"),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert insurance.provider_name == "AAR"
    assert (
        await profile_module.list_insurance(
            db=FakeAsyncSession([FakeScalarResult([insurance])]),
            current_user=user,
        )
    )[0].policy_number == "POL-1"
    await profile_module.delete_insurance(
        insurance_id=insurance.id,
        db=FakeAsyncSession([FakeScalarResult([insurance])]),
        current_user=user,
    )

    family_history = await profile_module.create_family_history(
        data=FamilyHistoryCreate(relation="mother", condition="Diabetes"),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert family_history.condition == "Diabetes"
    assert (
        await profile_module.list_family_history(
            db=FakeAsyncSession([FakeScalarResult([family_history])]),
            current_user=user,
        )
    )[0].relation == "mother"
    await profile_module.delete_family_history(
        history_id=family_history.id,
        db=FakeAsyncSession([FakeScalarResult([family_history])]),
        current_user=user,
    )

    vaccination = await profile_module.create_vaccination(
        data=VaccinationCreate(
            vaccine_name="Influenza",
            dose_number=1,
            date_administered=date(2025, 10, 1),
        ),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert vaccination.vaccine_name == "Influenza"
    assert (
        await profile_module.list_vaccinations(
            db=FakeAsyncSession([FakeScalarResult([vaccination])]),
            current_user=user,
        )
    )[0].dose_number == 1
    await profile_module.delete_vaccination(
        vaccination_id=vaccination.id,
        db=FakeAsyncSession([FakeScalarResult([vaccination])]),
        current_user=user,
    )

    growth = await profile_module.create_growth_measurement(
        data=GrowthMeasurementCreate(
            measurement_date=date(2026, 3, 1),
            age_months=24,
            height_cm=90.5,
            weight_kg=13.2,
        ),
        db=FakeAsyncSession(),
        current_user=user,
    )
    assert growth.age_months == 24
    assert (
        await profile_module.list_growth_measurements(
            db=FakeAsyncSession([FakeScalarResult([growth])]),
            current_user=user,
        )
    )[0].height_cm == 90.5
    await profile_module.delete_growth_measurement(
        measurement_id=growth.id,
        db=FakeAsyncSession([FakeScalarResult([growth])]),
        current_user=user,
    )
