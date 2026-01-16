from datetime import datetime

from pydantic import BaseModel, Field


class RecordBase(BaseModel):
    """Base schema for medical records."""
    
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    record_type: str = Field(default="general", max_length=50)


class RecordCreate(RecordBase):
    """Schema for creating a new medical record."""
    pass


class RecordResponse(RecordBase):
    """Schema for medical record response."""
    
    id: int
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True
