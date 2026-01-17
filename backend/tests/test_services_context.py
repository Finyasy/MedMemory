from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.context.analyzer import QueryAnalyzer, QueryIntent
from app.services.context.engine import ContextEngine
from app.services.context.ranker import ContextRanker
from app.services.context.retriever import RetrievalResult, RetrievalResponse, HybridRetriever
from app.services.context.synthesizer import ContextSynthesizer


def test_query_analyzer_extracts_sources_and_temporal():
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze("Any recent labs for A1C?")

    assert analysis.intent in {QueryIntent.RECENT, QueryIntent.GENERAL}
    assert analysis.temporal.is_temporal is True
    assert analysis.data_sources
    assert analysis.keywords


class DummyRetriever(HybridRetriever):
    async def _semantic_search(self, *args, **kwargs):
        return [
            RetrievalResult(
                id=1,
                content="Lab A",
                source_type="lab_result",
                source_id=1,
                patient_id=1,
                semantic_score=0.8,
                context_date=datetime.now(timezone.utc),
            )
        ]

    async def _keyword_search(self, *args, **kwargs):
        return [
            RetrievalResult(
                id=2,
                content="Med B",
                source_type="medication",
                source_id=2,
                patient_id=1,
                keyword_score=0.6,
                context_date=datetime.now(timezone.utc),
            )
        ]

    async def _structured_search(self, *args, **kwargs):
        return []


@pytest.mark.anyio
async def test_hybrid_retriever_combines_results():
    retriever = DummyRetriever(db=None, embedding_service=None)
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze("show labs")
    analysis.use_keyword_search = True
    analysis.keywords = ["labs"]

    response = await retriever.retrieve(analysis, patient_id=1, limit=5)

    assert isinstance(response, RetrievalResponse)
    assert response.total_combined >= 1


def test_context_ranker_filters_duplicates():
    ranker = ContextRanker(diversity_threshold=0.1)
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze("list labs")

    results = [
        RetrievalResult(
            id=1,
            content="Same content",
            source_type="lab_result",
            source_id=1,
            patient_id=1,
            combined_score=0.9,
            semantic_score=0.9,
        ),
        RetrievalResult(
            id=2,
            content="Same content",
            source_type="lab_result",
            source_id=2,
            patient_id=1,
            combined_score=0.8,
            semantic_score=0.8,
        ),
    ]

    ranked = ranker.rank(results, analysis, max_results=2)

    assert ranked
    assert len(ranked) == 1


def test_context_synthesizer_builds_prompt():
    synthesizer = ContextSynthesizer(max_tokens=200)
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze("summary")

    ranked = []
    context = synthesizer.synthesize(ranked, analysis)

    assert "No relevant information" in context.full_context
    prompt = synthesizer.create_prompt_context(context)
    assert "PATIENT CONTEXT" in prompt


@pytest.mark.anyio
async def test_context_engine_search_returns_dicts(monkeypatch):
    engine = ContextEngine(db=None)

    async def fake_retrieve(*_args, **_kwargs):
        return RetrievalResponse(
            results=[
                RetrievalResult(
                    id=1,
                    content="Content",
                    source_type="lab_result",
                    source_id=1,
                    patient_id=1,
                    combined_score=0.5,
                )
            ],
            total_combined=1,
        )

    monkeypatch.setattr(engine.retriever, "retrieve", fake_retrieve)

    results = await engine.search("query", patient_id=1, limit=5)

    assert results
    assert results[0]["source_type"] == "lab_result"
