from fastapi import APIRouter

from app.schemas.records import RecordCreate, RecordResponse

router = APIRouter(prefix="/records", tags=["Medical Records"])


# In-memory storage for demo (replace with database later)
_records: list[dict] = []


@router.get("/", response_model=list[RecordResponse])
async def list_records():
    """List all medical records."""
    return _records


@router.post("/", response_model=RecordResponse, status_code=201)
async def create_record(record: RecordCreate):
    """Create a new medical record."""
    new_record = {
        "id": len(_records) + 1,
        **record.model_dump()
    }
    _records.append(new_record)
    return new_record


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(record_id: int):
    """Get a specific medical record by ID."""
    for record in _records:
        if record["id"] == record_id:
            return record
    return {"error": "Record not found"}
