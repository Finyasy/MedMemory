"""Record repository implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

from sqlalchemy import select
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Patient, Record
from app.schemas.records import RecordCreate


class RecordRepository(Protocol):
    async def list_records(
        self,
        patient_id: Optional[int],
        owner_user_id: Optional[int],
        record_type: Optional[str],
        skip: int,
        limit: int,
    ) -> list:
        ...

    async def create_record(self, patient_id: int, record: RecordCreate):
        ...

    async def get_record(self, record_id: int):
        ...

    async def delete_record(self, record_id: int) -> bool:
        ...


class SQLRecordRepository:
    """Record repository backed by SQLAlchemy."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_records(
        self,
        patient_id: Optional[int],
        owner_user_id: Optional[int],
        record_type: Optional[str],
        skip: int,
        limit: int,
    ) -> list[Record]:
        query = select(Record).options(
            load_only(
                Record.id,
                Record.patient_id,
                Record.title,
                Record.content,
                Record.record_type,
                Record.created_at,
                Record.updated_at,
            )
        )

        if owner_user_id is not None:
            query = query.join(Patient).where(Patient.user_id == owner_user_id)

        if patient_id:
            query = query.where(Record.patient_id == patient_id)

        if record_type:
            query = query.where(Record.record_type == record_type)

        query = query.order_by(Record.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_record(self, patient_id: int, record: RecordCreate) -> Record:
        patient_result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        if not patient_result.scalar_one_or_none():
            raise ValueError("Patient not found")

        new_record = Record(
            patient_id=patient_id,
            title=record.title,
            content=record.content,
            record_type=record.record_type,
        )

        self.db.add(new_record)
        await self.db.flush()
        await self.db.refresh(new_record)
        return new_record

    async def get_record(self, record_id: int) -> Optional[Record]:
        result = await self.db.execute(
            select(Record).where(Record.id == record_id)
        )
        return result.scalar_one_or_none()

    async def delete_record(self, record_id: int) -> bool:
        record = await self.get_record(record_id)
        if not record:
            return False
        await self.db.delete(record)
        return True


@dataclass
class InMemoryRecord:
    id: int
    patient_id: int
    title: str
    content: str
    record_type: str
    created_at: datetime
    updated_at: datetime


class InMemoryRecordRepository:
    """In-memory repository for tests and local demos."""

    def __init__(self):
        self._records: list[InMemoryRecord] = []
        self._next_id = 1

    async def list_records(
        self,
        patient_id: Optional[int],
        owner_user_id: Optional[int],
        record_type: Optional[str],
        skip: int,
        limit: int,
    ) -> list[InMemoryRecord]:
        records = self._records

        if patient_id is not None:
            records = [r for r in records if r.patient_id == patient_id]

        if record_type:
            records = [r for r in records if r.record_type == record_type]

        return records[skip : skip + limit]

    async def create_record(self, patient_id: int, record: RecordCreate) -> InMemoryRecord:
        now = datetime.now(timezone.utc)
        new_record = InMemoryRecord(
            id=self._next_id,
            patient_id=patient_id,
            title=record.title,
            content=record.content,
            record_type=record.record_type,
            created_at=now,
            updated_at=now,
        )
        self._records.append(new_record)
        self._next_id += 1
        return new_record

    async def get_record(self, record_id: int) -> Optional[InMemoryRecord]:
        for record in self._records:
            if record.id == record_id:
                return record
        return None

    async def delete_record(self, record_id: int) -> bool:
        for idx, record in enumerate(self._records):
            if record.id == record_id:
                del self._records[idx]
                return True
        return False

    def clear(self) -> None:
        self._records.clear()
        self._next_id = 1
