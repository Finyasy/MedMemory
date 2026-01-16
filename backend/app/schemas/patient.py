from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PatientBase(BaseModel):
    """Base schema for patient data."""
    
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    blood_type: Optional[str] = Field(None, max_length=10)
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None


class PatientCreate(PatientBase):
    """Schema for creating a new patient."""
    
    external_id: Optional[str] = Field(None, max_length=100)


class PatientUpdate(BaseModel):
    """Schema for updating a patient (all fields optional)."""
    
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    blood_type: Optional[str] = Field(None, max_length=10)
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None


class PatientResponse(PatientBase):
    """Schema for patient response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    full_name: str
    age: Optional[int] = None


class PatientSummary(BaseModel):
    """Brief patient summary for lists."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
