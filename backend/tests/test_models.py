from datetime import date

from app.models.medication import Medication
from app.models.patient import Patient


def test_patient_full_name_and_age():
    today = date.today()
    birth_date = date(today.year - 30, today.month, today.day)
    patient = Patient(
        first_name="Ada", last_name="Lovelace", date_of_birth=birth_date, user_id=1
    )

    assert patient.full_name == "Ada Lovelace"
    assert patient.age == 30


def test_patient_age_without_birth_date():
    patient = Patient(
        first_name="Ada", last_name="Lovelace", date_of_birth=None, user_id=1
    )

    assert patient.age is None


def test_medication_is_current_active_without_end_date():
    med = Medication(name="Atorvastatin", patient_id=1, is_active=True)

    assert med.is_current is True


def test_medication_is_current_inactive_or_ended():
    today = date.today()
    ended = Medication(
        name="Amoxicillin",
        patient_id=1,
        is_active=True,
        end_date=today.replace(year=today.year - 1),
    )
    inactive = Medication(name="Metformin", patient_id=1, is_active=False)

    assert ended.is_current is False
    assert inactive.is_current is False
