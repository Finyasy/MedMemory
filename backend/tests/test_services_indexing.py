from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models import Document, Encounter, LabResult, Medication, MemoryChunk
from app.services.embeddings.indexing import MemoryIndexingService


class _FakeScalars:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _FakeResult:
    def __init__(self, *, scalars=None, scalar=None, rowcount=0):
        self._scalars = list(scalars or [])
        self._scalar = scalar
        self.rowcount = rowcount

    def scalars(self):
        return _FakeScalars(self._scalars)

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDB:
    def __init__(self, execute_results=None):
        self._execute_results = list(execute_results or [])
        self.added: list[object] = []
        self.flush_calls = 0

    async def execute(self, *_args, **_kwargs):
        if not self._execute_results:
            return _FakeResult()
        return self._execute_results.pop(0)

    def add(self, instance):
        self.added.append(instance)

    async def flush(self):
        self.flush_calls += 1


class _FakeEmbeddingService:
    model_name = "fake-embedding-model"

    def __init__(self):
        self.embed_texts_calls: list[list[str]] = []
        self.embed_text_calls: list[str] = []

    async def embed_texts_async(self, texts):
        self.embed_texts_calls.append(list(texts))
        return [[float(index), float(index) + 0.5] for index, _ in enumerate(texts, 1)]

    async def embed_text_async(self, text):
        self.embed_text_calls.append(text)
        return [9.0, 1.0]


class _FakeChunker:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.calls: list[tuple[str, str]] = []

    def chunk_text(self, content: str, source_type: str):
        self.calls.append((content, source_type))
        return list(self._chunks)


@pytest.mark.anyio
async def test_index_text_returns_empty_for_blank_content():
    db = _FakeDB()
    embedding_service = _FakeEmbeddingService()
    service = MemoryIndexingService(
        db=db,
        embedding_service=embedding_service,
        chunker=_FakeChunker([]),
    )

    chunks = await service.index_text(
        patient_id=1,
        content="   ",
        source_type="document",
    )

    assert chunks == []
    assert embedding_service.embed_texts_calls == []
    assert db.added == []


@pytest.mark.anyio
async def test_index_text_creates_memory_chunks_with_embeddings():
    db = _FakeDB()
    embedding_service = _FakeEmbeddingService()
    chunker = _FakeChunker(
        [
            SimpleNamespace(content="Chunk A", content_hash="hash-a"),
            SimpleNamespace(content="Chunk B", content_hash="hash-b"),
        ]
    )
    service = MemoryIndexingService(
        db=db,
        embedding_service=embedding_service,
        chunker=chunker,
    )

    chunks = await service.index_text(
        patient_id=4,
        content="Original content",
        source_type="document",
        source_id=11,
        source_table="documents",
        context_date=datetime(2026, 3, 10, tzinfo=UTC),
        chunk_type="summary",
        importance_score=0.9,
        metadata={"section": "overview"},
    )

    assert chunker.calls == [("Original content", "document")]
    assert embedding_service.embed_texts_calls == [["Chunk A", "Chunk B"]]
    assert len(chunks) == 2
    assert all(isinstance(chunk, MemoryChunk) for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert chunks[0].embedding == [1.0, 1.5]
    assert chunks[1].embedding == [2.0, 2.5]
    assert chunks[0].metadata_json == "{'section': 'overview'}"
    assert chunks[0].embedding_model == "fake-embedding-model"
    assert chunks[0].is_indexed is True
    assert db.flush_calls == 1
    assert db.added == chunks


@pytest.mark.anyio
async def test_index_record_helpers_delegate_with_expected_content():
    service = MemoryIndexingService(
        db=_FakeDB(),
        embedding_service=_FakeEmbeddingService(),
        chunker=_FakeChunker([]),
    )
    calls: list[dict] = []

    async def _fake_index_text(**kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(id=len(calls))]

    service.index_text = _fake_index_text  # type: ignore[method-assign]

    lab = LabResult(
        id=2,
        patient_id=9,
        test_name="Hemoglobin",
        value="8.2",
        unit="g/dL",
        reference_range="12-16",
        status="abnormal",
        is_abnormal=True,
        notes="Repeat in one week",
        category="hematology",
        collected_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    medication = Medication(
        id=3,
        patient_id=9,
        name="Lisinopril",
        generic_name="Lisinopril",
        dosage="10 mg",
        frequency="daily",
        route="oral",
        indication="Blood pressure",
        drug_class="ACE inhibitor",
        is_active=True,
        instructions="Take with water",
        prescriber="Dr. Lee",
        prescribed_at=datetime(2026, 3, 2, tzinfo=UTC),
    )
    encounter = Encounter(
        id=4,
        patient_id=9,
        encounter_type="office_visit",
        encounter_date=datetime(2026, 3, 3, tzinfo=UTC),
        provider_name="Dr. Chen",
        provider_specialty="Cardiology",
        chief_complaint="Chest pain",
        objective="Normal exam",
        assessment="Stable",
        plan="Follow up",
        clinical_notes="Patient improving",
        vital_blood_pressure="120/80",
        vital_heart_rate=72,
        vital_temperature=98.6,
    )

    await service.index_lab_result(lab)
    await service.index_medication(medication)
    await service.index_encounter(encounter)

    assert len(calls) == 3
    assert "⚠️ ABNORMAL RESULT" in calls[0]["content"]
    assert calls[0]["importance_score"] == 0.8
    assert "Medication: Lisinopril" in calls[1]["content"]
    assert "Status: Active" in calls[1]["content"]
    assert calls[1]["importance_score"] == 0.7
    assert "Medical Visit: Office Visit" in calls[2]["content"]
    assert "Vitals: BP: 120/80, HR: 72, Temp: 98.6°F" in calls[2]["content"]
    assert calls[2]["chunk_type"] == "clinical_note"


@pytest.mark.anyio
async def test_index_document_chunks_updates_unindexed_rows():
    chunk_a = MemoryChunk(
        patient_id=5,
        content="Document chunk A",
        content_hash="chunk-a",
        source_type="document",
        source_id=12,
        is_indexed=False,
    )
    chunk_b = MemoryChunk(
        patient_id=5,
        content="Document chunk B",
        content_hash="chunk-b",
        source_type="document",
        source_id=12,
        is_indexed=False,
    )
    db = _FakeDB(execute_results=[_FakeResult(scalars=[chunk_a, chunk_b])])
    embedding_service = _FakeEmbeddingService()
    service = MemoryIndexingService(
        db=db,
        embedding_service=embedding_service,
        chunker=_FakeChunker([]),
    )
    document = Document(
        id=12,
        patient_id=5,
        filename="report.pdf",
        original_filename="report.pdf",
        file_path="/tmp/report.pdf",
        document_type="lab_report",
        received_date=datetime(2026, 3, 5, tzinfo=UTC),
    )

    updated_chunks = await service.index_document_chunks(document)

    assert updated_chunks == [chunk_a, chunk_b]
    assert embedding_service.embed_texts_calls == [["Document chunk A", "Document chunk B"]]
    assert chunk_a.is_indexed is True
    assert chunk_b.embedding_model == "fake-embedding-model"
    assert db.flush_calls == 1


@pytest.mark.anyio
async def test_index_all_for_patient_aggregates_counts(monkeypatch):
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalars=[LabResult(patient_id=1, test_name="CBC")]),
            _FakeResult(scalars=[Medication(patient_id=1, name="Metformin")]),
            _FakeResult(
                scalars=[
                    Encounter(
                        patient_id=1,
                        encounter_type="office_visit",
                        encounter_date=datetime(2026, 3, 7, tzinfo=UTC),
                    )
                ]
            ),
            _FakeResult(
                scalars=[
                    Document(
                        patient_id=1,
                        filename="report.pdf",
                        original_filename="report.pdf",
                        file_path="/tmp/report.pdf",
                        document_type="lab_report",
                        received_date=datetime(2026, 3, 7, tzinfo=UTC),
                        is_processed=True,
                    )
                ]
            ),
        ]
    )
    service = MemoryIndexingService(
        db=db,
        embedding_service=_FakeEmbeddingService(),
        chunker=_FakeChunker([]),
    )

    async def _fake_lab(_lab):
        return [1, 2]

    async def _fake_med(_med):
        return [1]

    async def _fake_encounter(_encounter):
        return [1, 2, 3]

    async def _fake_document(_doc):
        return [1]

    monkeypatch.setattr(service, "index_lab_result", _fake_lab)
    monkeypatch.setattr(service, "index_medication", _fake_med)
    monkeypatch.setattr(service, "index_encounter", _fake_encounter)
    monkeypatch.setattr(service, "index_document_chunks", _fake_document)

    stats = await service.index_all_for_patient(1)

    assert stats == {
        "lab_results": 1,
        "medications": 1,
        "encounters": 1,
        "documents": 1,
        "total_chunks": 7,
    }


@pytest.mark.anyio
async def test_reindex_chunk_updates_embedding_and_delete_returns_rowcount():
    chunk = MemoryChunk(
        id=55,
        patient_id=1,
        content="Needs new embedding",
        content_hash="rehash",
        source_type="document",
    )
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalar=chunk),
            _FakeResult(rowcount=4),
        ]
    )
    embedding_service = _FakeEmbeddingService()
    service = MemoryIndexingService(
        db=db,
        embedding_service=embedding_service,
        chunker=_FakeChunker([]),
    )

    reindexed = await service.reindex_chunk(55)
    deleted = await service.delete_patient_memory(1)

    assert reindexed is chunk
    assert chunk.embedding == [9.0, 1.0]
    assert chunk.embedding_model == "fake-embedding-model"
    assert embedding_service.embed_text_calls == ["Needs new embedding"]
    assert deleted == 4


@pytest.mark.anyio
async def test_reindex_chunk_raises_for_missing_chunk():
    service = MemoryIndexingService(
        db=_FakeDB(execute_results=[_FakeResult(scalar=None)]),
        embedding_service=_FakeEmbeddingService(),
        chunker=_FakeChunker([]),
    )

    with pytest.raises(ValueError, match="Chunk 404 not found"):
        await service.reindex_chunk(404)
