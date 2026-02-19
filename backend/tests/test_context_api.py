from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import context as context_api
from app.schemas.context import ContextRequest, QuickSearchRequest, SimpleContextRequest


class FakeResult:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])

    async def execute(self, *_args, **_kwargs):
        if not self._results:
            return FakeResult(None)
        return self._results.pop(0)


@pytest.mark.anyio
async def test_context_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(context_api, "get_patient_for_user", _deny)

    with pytest.raises(HTTPException) as exc:
        await context_api.get_context(
            request=ContextRequest(patient_id=99, query="summary"),
            db=FakeDB(),
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_simple_context_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(context_api, "get_patient_for_user", _deny)

    with pytest.raises(HTTPException) as exc:
        await context_api.get_simple_context(
            request=SimpleContextRequest(patient_id=99, query="summary"),
            db=FakeDB(),
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_analyze_query_returns_fields(monkeypatch):
    fake_temporal = SimpleNamespace(
        is_temporal=False,
        time_range=None,
        date_from=None,
        date_to=None,
        relative_days=None,
    )
    fake_analysis = SimpleNamespace(
        original_query="What meds?",
        normalized_query="what meds",
        intent=SimpleNamespace(value="medication_query"),
        confidence=0.8,
        medical_entities=["medication"],
        medication_names=["Aspirin"],
        test_names=[],
        condition_names=[],
        temporal=fake_temporal,
        data_sources=[SimpleNamespace(value="medications")],
        keywords=["meds"],
        use_semantic_search=True,
        use_keyword_search=True,
        boost_recent=False,
    )

    class FakeEngine:
        def __init__(self, *_args, **_kwargs):
            pass

        async def analyze_query(self, _query):
            return fake_analysis

    monkeypatch.setattr(context_api, "ContextEngine", FakeEngine)

    response = await context_api.analyze_query(
        query="What meds?",
        db=FakeDB(),
        current_user=SimpleNamespace(id=1),
    )

    assert response.intent == "medication_query"
    assert response.confidence == 0.8
    assert response.medication_names == ["Aspirin"]


@pytest.mark.anyio
async def test_quick_search_missing_patient_returns_404(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(context_api, "get_patient_for_user", _deny)
    db = FakeDB(results=[FakeResult(None)])
    with pytest.raises(HTTPException) as exc:
        await context_api.quick_search(
            request=QuickSearchRequest(patient_id=123, query="labs"),
            db=db,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_quick_search_success(monkeypatch):
    class FakeEngine:
        def __init__(self, *_args, **_kwargs):
            pass

        async def search(self, **_kwargs):
            return [
                {
                    "id": 1,
                    "content": "Lab result",
                    "source_type": "lab_result",
                    "source_id": 10,
                    "score": 0.9,
                    "date": None,
                }
            ]

    monkeypatch.setattr(context_api, "ContextEngine", FakeEngine)

    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(context_api, "get_patient_for_user", _allow)
    db = FakeDB(results=[FakeResult(SimpleNamespace(id=1))])

    response = await context_api.quick_search(
        request=QuickSearchRequest(patient_id=1, query="labs"),
        db=db,
        current_user=SimpleNamespace(id=1),
    )

    assert response.total_results == 1
    assert response.results[0].source_type == "lab_result"


@pytest.mark.anyio
async def test_generate_prompt_missing_patient_returns_404(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(context_api, "get_patient_for_user", _deny)
    db = FakeDB(results=[FakeResult(None)])

    with pytest.raises(HTTPException) as exc:
        await context_api.generate_prompt(
            patient_id=123,
            question="question",
            db=db,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404
