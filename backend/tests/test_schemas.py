from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientUpdate
from app.schemas.records import RecordCreate, RecordResponse


def test_record_response_has_default_created_at():
    record = RecordResponse(
        id=1,
        patient_id=2,
        title="Lab Result",
        content="Normal",
        record_type="lab",
    )

    assert isinstance(record.created_at, datetime)


def test_record_create_requires_title_and_content():
    with pytest.raises(ValidationError):
        RecordCreate(title="", content="valid")

    with pytest.raises(ValidationError):
        RecordCreate(title="Valid", content="")


def test_patient_update_allows_empty_payload():
    payload = PatientUpdate()

    assert payload.model_dump(exclude_unset=True) == {}
