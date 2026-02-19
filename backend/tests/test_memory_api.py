from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import memory as memory_api
from app.models import User
from app.schemas.memory import ContextRequest, IndexTextRequest, SimilarChunksRequest


class FakeResult:
    def __init__(self, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars)


class FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])

    async def execute(self, *_args, **_kwargs):
        if not self._results:
            return FakeResult()
        return self._results.pop(0)

    async def delete(self, *_args, **_kwargs):
        return None


def _fake_user():
    return User(
        id=1,
        email="user@example.com",
        hashed_password="hashed",
        full_name="User",
        is_active=True,
    )


@pytest.mark.anyio
async def test_search_patient_history_denies_unowned(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(memory_api, "get_patient_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.search_patient_history(
            patient_id=99,
            query="labs",
            limit=5,
            min_similarity=0.3,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_index_patient_records_denies_unowned(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(memory_api, "get_patient_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.index_patient_records(
            patient_id=99,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_list_chunks_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(memory_api, "get_patient_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.list_memory_chunks(
            patient_id=99,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_get_chunk_denies_unowned(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Chunk not found")

    monkeypatch.setattr(memory_api, "_get_chunk_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.get_memory_chunk(
            chunk_id=10,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_context_builds_chunk_count(monkeypatch):
    class FakeSearchService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def get_patient_context(self, **_kwargs):
            return "---chunk---\nA\n---chunk---\nB"

    monkeypatch.setattr(memory_api, "SimilaritySearchService", FakeSearchService)

    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(memory_api, "get_patient_for_user", _allow)

    db = FakeDB()
    request = ContextRequest(
        patient_id=1, question="Summary?", max_chunks=10, max_tokens=1000
    )
    response = await memory_api.get_context_for_question(
        request=request,
        db=db,
        current_user=_fake_user(),
    )

    assert response.num_chunks == 5
    assert response.context_length == len(response.context)


@pytest.mark.anyio
async def test_find_similar_chunks_denies_unowned(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Chunk not found")

    monkeypatch.setattr(memory_api, "_get_chunk_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.find_similar_chunks(
            request=SimilarChunksRequest(chunk_id=50, limit=5, same_patient_only=True),
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_index_custom_text_returns_count(monkeypatch):
    class FakeIndexingService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def index_text(self, **_kwargs):
            return [1, 2, 3]

    monkeypatch.setattr(memory_api, "MemoryIndexingService", FakeIndexingService)

    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(memory_api, "get_patient_for_user", _allow)
    db = FakeDB()
    request = IndexTextRequest(patient_id=1, content="note", source_type="custom")
    response = await memory_api.index_custom_text(
        request=request, db=db, current_user=_fake_user()
    )
    assert response.total_chunks == 3


@pytest.mark.anyio
async def test_memory_stats_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(memory_api, "get_patient_for_user", _deny)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await memory_api.get_memory_stats(
            patient_id=99, db=db, current_user=_fake_user()
        )

    assert exc.value.status_code == 404
