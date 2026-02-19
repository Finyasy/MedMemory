from __future__ import annotations

import numpy as np
import pytest

from app.services.embeddings.embedding import (
    EmbeddingService,
    MissingMLDependencyError,
)
from app.services.embeddings.search import (
    SearchResponse,
    SearchResult,
    SimilaritySearchService,
)


class DummyModel:
    def encode(
        self, texts, convert_to_numpy=True, normalize_embeddings=True, **_kwargs
    ):
        if isinstance(texts, str):
            return np.array([1.0, 0.0, 0.0])
        return np.array([[1.0, 0.0, 0.0] for _ in texts])

    def get_sentence_embedding_dimension(self):
        return 3


def test_embedding_service_embed_and_similarity(monkeypatch):
    service = EmbeddingService(model_name="dummy")
    monkeypatch.setattr(service, "_load_model", lambda: DummyModel())

    embedding = service.embed_text("hello")
    embeddings = service.embed_texts(["a", "b", " "])

    assert embedding == [1.0, 0.0, 0.0]
    assert embeddings == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert service.compute_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_embedding_service_missing_dependency_error_message(monkeypatch):
    import builtins

    service = object.__new__(EmbeddingService)
    service.model_name = "all-MiniLM-L6-v2"
    service.device = "cpu"

    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sentence_transformers":
            raise ModuleNotFoundError(
                "No module named 'requests'",
                name="requests",
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(MissingMLDependencyError) as exc:
        service._load_model()

    message = str(exc.value)
    assert "Missing required ML dependency 'requests'" in message
    assert "cd backend && uv sync" in message


class DummySearchService(SimilaritySearchService):
    async def search_patient_history(
        self, patient_id: int, query: str, limit: int = 10, min_similarity: float = 0.3
    ):
        return SearchResponse(
            query=query,
            results=[
                SearchResult(
                    chunk_id=1,
                    patient_id=patient_id,
                    content="Result A",
                    source_type="lab_result",
                    source_id=1,
                    similarity_score=0.9,
                    context_date=None,
                    chunk_type=None,
                ),
                SearchResult(
                    chunk_id=2,
                    patient_id=patient_id,
                    content="Result B",
                    source_type="medication",
                    source_id=2,
                    similarity_score=0.8,
                    context_date=None,
                    chunk_type=None,
                ),
            ],
            total_results=2,
            search_time_ms=1.0,
        )


class DummyDB:
    pass


@pytest.mark.anyio
async def test_similarity_search_context_building():
    service = DummySearchService(DummyDB())
    context = await service.get_patient_context(
        patient_id=1, query="test", max_chunks=2, max_tokens=50
    )

    assert "Result A" in context
    assert "Result B" in context
