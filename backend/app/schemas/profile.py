"""Pydantic schemas for profile and dependent management."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# === Emergency Info ===


class EmergencyInfoBase(BaseModel):
    medical_alert: str | None = None
    organ_donor: bool | None = None
    dnr_status: bool | None = None
    preferred_hospital: str | None = Field(None, max_length=255)


class EmergencyInfoUpdate(EmergencyInfoBase):
    pass


class EmergencyInfoResponse(EmergencyInfoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Emergency Contacts ===


class EmergencyContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    relationship: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr | None = None
    is_primary: bool = False


class EmergencyContactCreate(EmergencyContactBase):
    pass


class EmergencyContactUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    relationship: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=1, max_length=20)
    email: EmailStr | None = None
    is_primary: bool | None = None


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    name: str
    relationship: str
    phone: str
    email: EmailStr | None = None
    is_primary: bool


# === Allergies ===


class AllergyBase(BaseModel):
    allergen: str = Field(..., min_length=1, max_length=255)
    allergy_type: str = Field(..., pattern="^(food|drug|environmental|other)$")
    severity: str = Field(..., pattern="^(mild|moderate|severe|life_threatening)$")
    reaction: str | None = None
    diagnosed_date: date | None = None
    notes: str | None = None


class AllergyCreate(AllergyBase):
    pass


class AllergyUpdate(BaseModel):
    allergen: str | None = Field(None, min_length=1, max_length=255)
    allergy_type: str | None = Field(None, pattern="^(food|drug|environmental|other)$")
    severity: str | None = Field(
        None, pattern="^(mild|moderate|severe|life_threatening)$"
    )
    reaction: str | None = None
    diagnosed_date: date | None = None
    notes: str | None = None


class AllergyResponse(AllergyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    created_at: datetime


# === Conditions ===


class ConditionBase(BaseModel):
    condition_name: str = Field(..., min_length=1, max_length=255)
    icd_code: str | None = Field(None, max_length=20)
    diagnosed_date: date | None = None
    status: str = Field(default="active", pattern="^(active|resolved|in_remission)$")
    severity: str | None = Field(None, pattern="^(mild|moderate|severe)$")
    treating_physician: str | None = Field(None, max_length=255)
    notes: str | None = None


class ConditionCreate(ConditionBase):
    pass


class ConditionUpdate(BaseModel):
    condition_name: str | None = Field(None, min_length=1, max_length=255)
    icd_code: str | None = Field(None, max_length=20)
    diagnosed_date: date | None = None
    status: str | None = Field(None, pattern="^(active|resolved|in_remission)$")
    severity: str | None = Field(None, pattern="^(mild|moderate|severe)$")
    treating_physician: str | None = Field(None, max_length=255)
    notes: str | None = None


class ConditionResponse(ConditionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    created_at: datetime


# === Healthcare Providers ===


class ProviderBase(BaseModel):
    provider_type: str = Field(
        ..., pattern="^(pcp|specialist|dentist|pharmacy|hospital|other)$"
    )
    specialty: str | None = Field(None, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    clinic_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    fax: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    address: str | None = None
    is_primary: bool = False
    notes: str | None = None


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    provider_type: str | None = Field(
        None, pattern="^(pcp|specialist|dentist|pharmacy|hospital|other)$"
    )
    specialty: str | None = Field(None, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=255)
    clinic_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    fax: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    address: str | None = None
    is_primary: bool | None = None
    notes: str | None = None


class ProviderResponse(ProviderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Lifestyle ===


class LifestyleBase(BaseModel):
    smoking_status: str | None = Field(None, pattern="^(never|former|current)$")
    smoking_frequency: str | None = Field(None, max_length=50)
    alcohol_use: str | None = Field(None, pattern="^(never|occasional|moderate|heavy)$")
    exercise_frequency: str | None = Field(
        None, pattern="^(none|light|moderate|active)$"
    )
    diet_type: str | None = Field(None, max_length=50)
    sleep_hours: Decimal | None = Field(None, ge=0, le=24)
    occupation: str | None = Field(None, max_length=255)
    stress_level: str | None = Field(None, pattern="^(low|moderate|high)$")


class LifestyleUpdate(LifestyleBase):
    pass


class LifestyleResponse(LifestyleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Insurance ===


class InsuranceBase(BaseModel):
    provider_name: str = Field(..., min_length=1, max_length=255)
    policy_number: str | None = Field(None, max_length=100)
    group_number: str | None = Field(None, max_length=100)
    subscriber_name: str | None = Field(None, max_length=255)
    subscriber_dob: date | None = None
    relationship_to_subscriber: str | None = Field(None, max_length=50)
    effective_date: date | None = None
    expiration_date: date | None = None
    is_primary: bool = True


class InsuranceCreate(InsuranceBase):
    pass


class InsuranceUpdate(BaseModel):
    provider_name: str | None = Field(None, min_length=1, max_length=255)
    policy_number: str | None = Field(None, max_length=100)
    group_number: str | None = Field(None, max_length=100)
    subscriber_name: str | None = Field(None, max_length=255)
    subscriber_dob: date | None = None
    relationship_to_subscriber: str | None = Field(None, max_length=50)
    effective_date: date | None = None
    expiration_date: date | None = None
    is_primary: bool | None = None


class InsuranceResponse(InsuranceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Family History ===


class FamilyHistoryBase(BaseModel):
    relation: str = Field(
        ..., pattern="^(mother|father|sibling|grandparent|aunt|uncle|cousin|other)$"
    )
    condition: str = Field(..., min_length=1, max_length=255)
    age_of_onset: int | None = Field(None, ge=0, le=150)
    is_deceased: bool = False
    notes: str | None = None


class FamilyHistoryCreate(FamilyHistoryBase):
    pass


class FamilyHistoryUpdate(BaseModel):
    relation: str | None = Field(
        None, pattern="^(mother|father|sibling|grandparent|aunt|uncle|cousin|other)$"
    )
    condition: str | None = Field(None, min_length=1, max_length=255)
    age_of_onset: int | None = Field(None, ge=0, le=150)
    is_deceased: bool | None = None
    notes: str | None = None


class FamilyHistoryResponse(FamilyHistoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Vaccinations ===


class VaccinationBase(BaseModel):
    vaccine_name: str = Field(..., min_length=1, max_length=255)
    dose_number: int | None = Field(None, ge=1, le=10)
    date_administered: date
    administered_by: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)
    lot_number: str | None = Field(None, max_length=100)
    expiration_date: date | None = None
    site: str | None = Field(None, max_length=50)
    reaction: str | None = None
    notes: str | None = None


class VaccinationCreate(VaccinationBase):
    pass


class VaccinationUpdate(BaseModel):
    vaccine_name: str | None = Field(None, min_length=1, max_length=255)
    dose_number: int | None = Field(None, ge=1, le=10)
    date_administered: date | None = None
    administered_by: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)
    lot_number: str | None = Field(None, max_length=100)
    expiration_date: date | None = None
    site: str | None = Field(None, max_length=50)
    reaction: str | None = None
    notes: str | None = None


class VaccinationResponse(VaccinationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Growth Measurements ===


class GrowthMeasurementBase(BaseModel):
    measurement_date: date
    age_months: int | None = Field(None, ge=0)
    height_cm: Decimal | None = Field(None, ge=0, le=300)
    weight_kg: Decimal | None = Field(None, ge=0, le=500)
    head_circumference_cm: Decimal | None = Field(None, ge=0, le=100)
    height_percentile: int | None = Field(None, ge=0, le=100)
    weight_percentile: int | None = Field(None, ge=0, le=100)
    bmi: Decimal | None = Field(None, ge=0, le=100)
    bmi_percentile: int | None = Field(None, ge=0, le=100)
    notes: str | None = None


class GrowthMeasurementCreate(GrowthMeasurementBase):
    pass


class GrowthMeasurementResponse(GrowthMeasurementBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int


# === Basic Profile Update ===


class BasicProfileUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = Field(None, pattern="^(male|female|other)$")
    gender: str | None = Field(None, max_length=20)
    blood_type: str | None = Field(
        None, pattern="^(A\\+|A-|B\\+|B-|AB\\+|AB-|O\\+|O-|unknown)$"
    )
    height_cm: Decimal | None = Field(None, ge=0, le=300)
    weight_kg: Decimal | None = Field(None, ge=0, le=500)
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    preferred_language: str | None = Field(None, max_length=10)
    timezone: str | None = Field(None, max_length=50)


# === Dependent Management ===


class DependentCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    sex: str | None = Field(None, pattern="^(male|female|other)$")
    blood_type: str | None = Field(
        None, pattern="^(A\\+|A-|B\\+|B-|AB\\+|AB-|O\\+|O-|unknown)$"
    )
    relationship_type: str = Field(
        ..., pattern="^(child|spouse|parent|sibling|guardian|other)$"
    )


class DependentUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = Field(None, pattern="^(male|female|other)$")
    blood_type: str | None = Field(
        None, pattern="^(A\\+|A-|B\\+|B-|AB\\+|AB-|O\\+|O-|unknown)$"
    )


class DependentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    age: int | None
    sex: str | None
    blood_type: str | None
    relationship_type: str
    is_primary_caretaker: bool
    can_edit: bool


# === Full Profile Response ===


class ProfileCompletionStatus(BaseModel):
    overall_percentage: int
    sections: dict[str, dict]


class FullProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Basic info
    id: int
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    age: int | None
    sex: str | None
    gender: str | None
    blood_type: str | None
    height_cm: Decimal | None
    weight_kg: Decimal | None
    phone: str | None
    email: str | None
    address: str | None
    preferred_language: str | None
    timezone: str | None
    profile_photo_url: str | None
    is_dependent: bool
    profile_completed_at: datetime | None

    # Related data
    emergency_info: EmergencyInfoResponse | None = None
    emergency_contacts: list[EmergencyContactResponse] = []
    allergies: list[AllergyResponse] = []
    conditions: list[ConditionResponse] = []
    providers: list[ProviderResponse] = []
    lifestyle: LifestyleResponse | None = None
    insurance: list[InsuranceResponse] = []
    family_history: list[FamilyHistoryResponse] = []
    vaccinations: list[VaccinationResponse] = []
    growth_measurements: list[GrowthMeasurementResponse] = []

    # Stats
    profile_completion: ProfileCompletionStatus | None = None


class FamilyOverviewMember(BaseModel):
    id: int
    full_name: str
    age: int | None
    sex: str | None
    blood_type: str | None
    relationship_type: str | None
    document_count: int = 0
    last_activity: datetime | None = None
    alerts: list[str] = []


class FamilyOverviewResponse(BaseModel):
    members: list[FamilyOverviewMember]
