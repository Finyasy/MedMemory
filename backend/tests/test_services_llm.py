from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.context.analyzer import QueryIntent
from app.services.llm.conversation import Conversation
from app.services.llm.evidence_validator import EvidenceValidator
from app.services.llm.model import LLMResponse, LLMService
from app.services.llm.rag import RAGService


@pytest.fixture(autouse=True)
def _reset_guardrail_counters():
    RAGService._global_guardrail_counters.clear()
    yield
    RAGService._global_guardrail_counters.clear()


def test_llm_response_total_tokens():
    response = LLMResponse(
        text="hi", tokens_generated=2, tokens_input=3, generation_time_ms=1.0
    )
    assert response.total_tokens == 5


def test_llm_prompt_builder_includes_history():
    service = LLMService(model_name="dummy")
    prompt = service._build_prompt(
        prompt="What now?",
        system_prompt="System prompt",
        conversation_history=[{"role": "user", "content": "Hello"}],
    )

    assert "System:" in prompt
    assert "User: Hello" in prompt
    assert "Assistant:" in prompt


def test_llm_model_info_without_loading():
    service = LLMService(model_name="dummy")

    class DummyTokenizer:
        def __len__(self):
            return 5

    service._tokenizer = DummyTokenizer()

    info = service.get_model_info()

    assert info["model_name"] == service.model_name
    assert info["vocab_size"] == 5
    assert info["do_sample"] is service.do_sample
    assert info["top_p"] == service.top_p
    assert info["top_k"] == service.top_k


class FakeConversationManager:
    def __init__(self):
        from uuid import uuid4

        self._conversation = Conversation(conversation_id=uuid4(), patient_id=1)

    async def get_conversation(self, _conversation_id):
        return self._conversation

    async def create_conversation(self, patient_id, title=None):
        self._conversation.patient_id = patient_id
        return self._conversation

    async def add_message(self, *args, **kwargs):
        role = kwargs.get("role") if "role" in kwargs else args[1]
        content = kwargs.get("content") if "content" in kwargs else args[2]
        structured_data = kwargs.get("structured_data")
        self._conversation.add_message(
            role,
            content,
            structured_data=structured_data,
        )
        return SimpleNamespace(message_id=1)


@dataclass
class FakeContextResult:
    prompt: str
    synthesized_context: SimpleNamespace
    ranked_results: list
    query_analysis: SimpleNamespace | None = None


class FakeContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Detailed context text", total_chunks_used=1
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(source_type="lab", source_id=1),
                    final_score=0.9,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.GENERAL,
                test_names=[],
                medication_names=[],
            ),
        )


class RecordingContextEngine(FakeContextEngine):
    def __init__(self):
        self.last_query = None
        self.last_system_prompt = None
        self.last_min_score = None

    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **kwargs,
    ):
        self.last_query = query
        self.last_system_prompt = system_prompt
        self.last_min_score = min_score
        return await super().get_context(
            query=query,
            patient_id=patient_id,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            min_score=min_score,
            **kwargs,
        )


class FakeLLMService:
    def __init__(self):
        self.last_history = None
        self.last_prompt = None

    async def generate(
        self,
        prompt,
        max_new_tokens=512,
        conversation_history=None,
        **_kwargs,
    ):
        self.last_history = conversation_history
        self.last_prompt = prompt
        return LLMResponse(
            text="Answer", tokens_generated=2, tokens_input=3, generation_time_ms=1.0
        )

    async def stream_generate(self, prompt, system_prompt=None, **_kwargs):
        for chunk in ["A", "B"]:
            yield chunk


class FakeGroundedNumericLLMService(FakeLLMService):
    async def generate(
        self,
        prompt,
        max_new_tokens=512,
        conversation_history=None,
        **_kwargs,
    ):
        self.last_history = conversation_history
        self.last_prompt = prompt
        return LLMResponse(
            text="Your hemoglobin is 10.1 g/dL.",
            tokens_generated=6,
            tokens_input=3,
            generation_time_ms=1.0,
        )


class FakeInvalidStructuredLLMService(FakeLLMService):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    async def generate(
        self,
        prompt,
        max_new_tokens=512,
        conversation_history=None,
        **_kwargs,
    ):
        self.call_count += 1
        self.last_history = conversation_history
        self.last_prompt = prompt
        return LLMResponse(
            text="This is not valid JSON",
            tokens_generated=6,
            tokens_input=3,
            generation_time_ms=1.0,
        )


class NeverCallLLMService(FakeLLMService):
    async def generate(self, *args, **kwargs):
        raise AssertionError("LLM generation should not be called in structured mode")


class NeverCallContextEngine:
    async def get_context(self, *args, **kwargs):
        raise AssertionError("Context retrieval should not be called for small talk")


@pytest.mark.anyio
async def test_rag_service_ask():
    llm = FakeLLMService()
    rag = RAGService(
        db=None,
        llm_service=llm,
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(question="What is CTX?", patient_id=1)

    assert response.answer == "Answer"
    assert response.num_sources == 1
    assert llm.last_history
    assert llm.last_history[-1]["role"] == "user"


@pytest.mark.anyio
async def test_rag_small_talk_returns_warm_direct_response():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=NeverCallContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(question="hey how was your day?", patient_id=1)

    assert "doing well" in response.answer.lower()
    assert "records" in response.answer.lower()
    assert response.num_sources == 0
    assert response.llm_response.finish_reason == "small_talk_direct"


@pytest.mark.anyio
async def test_rag_stream_small_talk_returns_warm_direct_response():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=NeverCallContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(question="hello", patient_id=1):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "ready to help" in chunks[0].lower()
    assert "lab results" in chunks[0].lower()


@pytest.mark.anyio
async def test_rag_ask_structured_small_talk_returns_text_without_structured_payload():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=NeverCallContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response, structured = await rag.ask_structured(
        question="thank you",
        patient_id=1,
    )

    assert structured is None
    assert "welcome" in response.answer.lower()
    assert response.llm_response.finish_reason == "small_talk_direct"


@pytest.mark.anyio
async def test_rag_greeting_plus_medical_question_still_uses_medical_path():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeStructuredContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="hey, what medications am i currently taking?",
        patient_id=1,
    )

    assert "Metformin" in response.answer
    assert response.llm_response.finish_reason == "structured_direct"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "expected_task_label"),
    [
        ("How has my HbA1c changed over time?", "TREND_ANALYSIS"),
        ("what medications am i currently taking?", "MEDICATION_RECONCILIATION"),
        ("is my lab result normal range?", "LAB_INTERPRETATION"),
    ],
)
async def test_rag_uses_routed_task_guidance_in_context_prompt(
    question, expected_task_label
):
    llm = FakeLLMService()
    context_engine = RecordingContextEngine()
    rag = RAGService(
        db=None,
        llm_service=llm,
        context_engine=context_engine,
        conversation_manager=FakeConversationManager(),
    )

    await rag.ask(question=question, patient_id=1)

    assert context_engine.last_min_score == pytest.approx(0.2)
    assert context_engine.last_system_prompt is not None
    assert expected_task_label in context_engine.last_system_prompt


@pytest.mark.anyio
async def test_rag_service_stream():
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(question="Q", patient_id=1):
        chunks.append(chunk)

    assert chunks == ["A", "B"]


@pytest.mark.anyio
async def test_rag_stream_uses_routed_task_guidance_in_context_prompt():
    context_engine = RecordingContextEngine()
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=context_engine,
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="How has my HbA1c changed over time?",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["A", "B"]
    assert context_engine.last_min_score == pytest.approx(0.2)
    assert context_engine.last_system_prompt is not None
    assert "TREND_ANALYSIS" in context_engine.last_system_prompt


@pytest.mark.anyio
async def test_rag_applies_warm_concise_profile_overlay_to_context_prompt(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_profile", "warm_concise_v1")
    context_engine = RecordingContextEngine()
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=context_engine,
        conversation_manager=FakeConversationManager(),
    )

    await rag.ask(
        question="what medications am i currently taking?",
        patient_id=1,
    )

    assert context_engine.last_system_prompt is not None
    assert "Tone profile: warm_concise_v1." in context_engine.last_system_prompt


@pytest.mark.anyio
async def test_rag_applies_clinician_humanized_profile_overlay(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_profile", "clinician_terse_humanized")
    context_engine = RecordingContextEngine()
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=context_engine,
        conversation_manager=FakeConversationManager(),
    )

    await rag.ask(
        question="latest hemoglobin value",
        patient_id=1,
        system_prompt=RAGService.CLINICIAN_SYSTEM_PROMPT,
    )

    assert context_engine.last_system_prompt is not None
    assert (
        "Tone profile: clinician_terse_humanized."
        in context_engine.last_system_prompt
    )


def test_rag_warm_concise_v2_tone_guardrail_deduplicates_repetition(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_profile", "warm_concise_v2")
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    cleaned = rag._apply_tone_guardrails(
        response_text=(
            "From your records, From your records, your hemoglobin is 10.1 g/dL.\n"
            "From your records, From your records, your hemoglobin is 10.1 g/dL."
        ),
        clinician_mode=False,
    )

    assert cleaned.count("From your records") == 1
    assert cleaned.count("10.1 g/dL") == 1


class FakeStructuredContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Medication: Metformin 500 mg (twice daily) - Active",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="medication",
                        source_id=1,
                        content="Medication: Metformin 500 mg (twice daily) - Active",
                    ),
                    final_score=0.95,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.LIST,
                test_names=[],
                medication_names=["metformin"],
            ),
        )


class FakeTrendStructuredContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context=("Lab: HbA1c = 7.4 %\nLab: HbA1c = 6.8 %"),
                total_chunks_used=2,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=10,
                        content="Lab: HbA1c = 7.4 %",
                        context_date=datetime(2025, 1, 10, tzinfo=UTC),
                    ),
                    final_score=0.96,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=12,
                        content="Lab: HbA1c = 6.8 %",
                        context_date=datetime(2025, 6, 10, tzinfo=UTC),
                    ),
                    final_score=0.94,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["HbA1c"],
                medication_names=[],
            ),
        )


class FakeTrendSinglePointContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Lab: HbA1c = 6.8 %",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=12,
                        content="Lab: HbA1c = 6.8 %",
                        context_date=datetime(2025, 6, 10, tzinfo=UTC),
                    ),
                    final_score=0.94,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["HbA1c"],
                medication_names=[],
            ),
        )


class FakeTrendBloodPressureContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Blood Pressure: 120/80 mmHg\nBlood Pressure: 130/85 mmHg",
                total_chunks_used=2,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=20,
                        content="Lab: Blood Pressure = 120/80 mmHg",
                        context_date=datetime(2025, 1, 10, tzinfo=UTC),
                    ),
                    final_score=0.96,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=22,
                        content="Lab: Blood Pressure = 130/85 mmHg",
                        context_date=datetime(2025, 6, 10, tzinfo=UTC),
                    ),
                    final_score=0.94,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["Blood Pressure"],
                medication_names=[],
            ),
        )


class FakeTrendPolarityContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="HIV: Non-Reactive\nHIV: Reactive",
                total_chunks_used=2,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=30,
                        content="Lab: HIV = Non-Reactive",
                        context_date=datetime(2025, 1, 10, tzinfo=UTC),
                    ),
                    final_score=0.95,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=31,
                        content="Lab: HIV = Reactive",
                        context_date=datetime(2025, 6, 10, tzinfo=UTC),
                    ),
                    final_score=0.94,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.STATUS,
                test_names=["HIV"],
                medication_names=[],
            ),
        )


class FakeAppleHealthContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context=(
                    "Apple Health daily steps: 4200 steps on 2026-03-04.\n"
                    "Apple Health daily steps: 5100 steps on 2026-03-06.\n"
                    "Apple Health daily steps: 0 steps on 2026-03-10.\n"
                    "Apple Health sync status: connected. Total synced days: 18. "
                    "Synced range: 2026-02-25 to 2026-03-10. "
                    "Last sync: 2026-03-10T18:32:00+00:00."
                ),
                total_chunks_used=4,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="apple_health",
                        source_id=201,
                        content="Apple Health daily steps: 4200 steps on 2026-03-04.",
                        context_date=datetime(2026, 3, 4, tzinfo=UTC),
                    ),
                    final_score=0.96,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="apple_health",
                        source_id=202,
                        content="Apple Health daily steps: 5100 steps on 2026-03-06.",
                        context_date=datetime(2026, 3, 6, tzinfo=UTC),
                    ),
                    final_score=0.95,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="apple_health",
                        source_id=203,
                        content="Apple Health daily steps: 0 steps on 2026-03-10.",
                        context_date=datetime(2026, 3, 10, tzinfo=UTC),
                    ),
                    final_score=0.94,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="apple_health_status",
                        source_id=301,
                        content=(
                            "Apple Health sync status: connected. Total synced days: 18. "
                            "Synced range: 2026-02-25 to 2026-03-10. "
                            "Last sync: 2026-03-10T18:32:00+00:00."
                        ),
                        context_date=datetime(2026, 3, 10, tzinfo=UTC),
                    ),
                    final_score=0.93,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.TREND,
                test_names=[],
                medication_names=[],
                data_sources=["apple_health"],
            ),
        )


class FakeMedicationPanelContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context=(
                    "Medication list update (2026-01-15)\n"
                    "Metformin 500 mg by mouth twice daily - Active\n"
                    "Lisinopril 10 mg daily - Active\n"
                    "Isoniazid 300 mg daily - Discontinued on 2026-01-15\n"
                    "No adverse drug reaction documented."
                ),
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="medication",
                        source_id=77,
                        content=(
                            "Medication list update (2026-01-15)\n"
                            "Metformin 500 mg by mouth twice daily - Active\n"
                            "Lisinopril 10 mg daily - Active\n"
                            "Isoniazid 300 mg daily - Discontinued on 2026-01-15\n"
                            "No adverse drug reaction documented."
                        ),
                    ),
                    final_score=0.96,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.LIST,
                test_names=[],
                medication_names=["metformin", "lisinopril", "isoniazid"],
            ),
        )


@pytest.mark.anyio
async def test_rag_service_uses_direct_structured_answer():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeStructuredContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what medications am i currently taking",
        patient_id=1,
    )

    assert "From your records" in response.answer
    assert "Metformin" in response.answer
    assert "(source: medication#1)" in response.answer
    assert response.llm_response.finish_reason == "structured_direct"
    assert rag.get_guardrail_counters().get("structured_direct") == 1


@pytest.mark.anyio
async def test_rag_stream_uses_direct_structured_answer():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeStructuredContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what medications am i currently taking",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "From your records" in chunks[0]
    assert "Metformin" in chunks[0]
    assert "(source: medication#1)" in chunks[0]
    assert rag.get_guardrail_counters().get("structured_direct") == 1


@pytest.mark.anyio
async def test_rag_direct_structured_discontinued_medication_answer():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeMedicationPanelContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="Which medication is marked as discontinued?",
        patient_id=1,
    )

    assert "discontinued" in response.answer.lower()
    assert "Isoniazid 300 mg daily - Discontinued on 2026-01-15" in response.answer


def test_rag_normalize_structured_content_prefers_fact_lines():
    rag = RAGService(
        db=None,
        llm_service=FakeLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    normalized = rag._normalize_structured_content(
        "Eval fixture - de-identified lab panel\n"
        "Date: 2026-01-12\n"
        "Hemoglobin: 10.1 g/dL (low)\n"
        "Notes: De-identified demo values normalized for product QA."
    )

    assert normalized == "Hemoglobin: 10.1 g/dL (low)"


@pytest.mark.anyio
async def test_rag_service_uses_direct_structured_trend_answer():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeTrendStructuredContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="How has my HbA1c changed over time?",
        patient_id=1,
    )

    assert "From your records, HbA1c changed from" in response.answer
    assert "2025-01-10" in response.answer
    assert "2025-06-10" in response.answer
    assert "decreased by 0.6 %" in response.answer


@pytest.mark.anyio
async def test_rag_service_direct_trend_requires_two_dated_values():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeTrendSinglePointContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="How has my HbA1c changed over time?",
        patient_id=1,
    )

    assert "not enough dated values to determine a trend" in response.answer.lower()


@pytest.mark.anyio
async def test_rag_service_direct_trend_handles_blood_pressure_ratios():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeTrendBloodPressureContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="How has my blood pressure changed over time?",
        patient_id=1,
    )

    assert "Blood Pressure changed from 120/80 mmHg on 2025-01-10" in response.answer
    assert "to 130/85 mmHg on 2025-06-10" in response.answer
    assert "systolic increased by 10 mmHg" in response.answer
    assert "diastolic increased by 5 mmHg" in response.answer


@pytest.mark.anyio
async def test_rag_service_direct_trend_handles_polarity_values():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeTrendPolarityContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="How has my HIV result changed over time?",
        patient_id=1,
    )

    assert "HIV changed from Non-Reactive to Reactive" in response.answer
    assert "between 2025-01-10 and 2025-06-10" in response.answer


@pytest.mark.anyio
async def test_rag_service_uses_direct_apple_health_answer():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeAppleHealthContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="Any Apple Health info across one week?",
        patient_id=1,
    )

    assert "Apple Health update" in response.answer
    assert "9,300 steps" in response.answer
    assert "averaging about 3,100 steps a day" in response.answer
    assert "latest recorded day was 2026-03-10 with 0 steps" in response.answer
    assert "18 synced day(s) overall" in response.answer
    assert response.llm_response.finish_reason == "structured_direct"


@pytest.mark.anyio
async def test_rag_service_recognizes_swahili_apple_health_question():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeAppleHealthContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="na mpangilio wa mienenendo ya apple health",
        patient_id=1,
    )

    assert "Apple Health update" in response.answer
    assert response.llm_response.finish_reason == "structured_direct"


@pytest.mark.anyio
async def test_rag_ask_structured_uses_direct_apple_health_answer():
    conversation_manager = FakeConversationManager()
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeAppleHealthContextEngine(),
        conversation_manager=conversation_manager,
    )

    response, structured = await rag.ask_structured(
        question="Any Apple Health info across one week?",
        patient_id=1,
    )

    assert structured is not None
    assert "Apple Health update" in response.answer
    assert "9,300 steps" in response.answer
    assert response.llm_response.finish_reason == "structured_direct"
    assert structured.overview.startswith("Apple Health logged 9,300 steps")
    assert [result.name for result in structured.key_results[:3]] == [
        "Total steps (2026-03-04 to 2026-03-10)",
        "Average daily steps",
        "Latest daily steps (2026-03-10)",
    ]
    assert structured.key_results[0].value == "9,300"
    assert "key_results" in structured.section_sources
    assert rag.get_guardrail_counters().get("structured_direct") == 1
    assert conversation_manager._conversation.messages[-1].structured_data is not None
    assert (
        conversation_manager._conversation.messages[-1].structured_data["overview"]
        == structured.overview
    )


class FakeNoContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(full_context="", total_chunks_used=0),
            ranked_results=[],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.GENERAL,
                test_names=[],
                medication_names=[],
            ),
        )


class FakeMissingPulseContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Visit note: vitals reviewed but not listed.",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=11,
                        content="Visit note: vitals reviewed but not listed.",
                    ),
                    final_score=0.8,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=[],
                medication_names=[],
            ),
        )


class FakeHallucinatingLLMService(FakeLLMService):
    async def generate(
        self,
        prompt,
        max_new_tokens=512,
        conversation_history=None,
        **_kwargs,
    ):
        self.last_history = conversation_history
        return LLMResponse(
            text="Your hemoglobin is 12.9 g/dL.",
            tokens_generated=8,
            tokens_input=3,
            generation_time_ms=1.0,
        )


class FakeHallucinatingNoStreamLLMService:
    async def generate(
        self,
        prompt,
        max_new_tokens=512,
        conversation_history=None,
        **_kwargs,
    ):
        return LLMResponse(
            text="Your hemoglobin is 12.9 g/dL.",
            tokens_generated=8,
            tokens_input=3,
            generation_time_ms=1.0,
        )


class FakeHighEvidenceFactContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Lab: Hemoglobin = 10.1 g/dL",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=10,
                        content="Lab: Hemoglobin = 10.1 g/dL",
                    ),
                    final_score=0.9,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["hemoglobin"],
                medication_names=[],
            ),
        )


class FakeClinicianContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Lab: Hemoglobin = 12.9 g/dL",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=88,
                        content="Lab: Hemoglobin = 12.9 g/dL",
                    ),
                    final_score=0.92,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["hemoglobin"],
                medication_names=[],
            ),
        )


class FakeAmbiguousCitationContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context=(
                    "Document A: Lab: Hemoglobin = 10.1 g/dL\n"
                    "Document B: Lab: Hemoglobin = 10.1 g/dL"
                ),
                total_chunks_used=2,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=10,
                        content="Document A: Lab: Hemoglobin = 10.1 g/dL",
                    ),
                    final_score=0.94,
                ),
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=11,
                        content="Document B: Lab: Hemoglobin = 10.1 g/dL",
                    ),
                    final_score=0.93,
                ),
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["hemoglobin"],
                medication_names=[],
            ),
        )


class FakeNoSourceNumericContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Lab: Hemoglobin = 12.9 g/dL",
                total_chunks_used=1,
            ),
            ranked_results=[],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.GENERAL,
                test_names=[],
                medication_names=[],
            ),
        )


@pytest.mark.anyio
async def test_rag_general_medical_no_evidence_returns_opt_in_message():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeNoContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="tell me about hiv vct",
        patient_id=1,
    )

    assert "general explanation" in response.answer
    assert response.llm_response.finish_reason == "general_medical_no_evidence"


@pytest.mark.anyio
async def test_rag_stream_general_medical_no_evidence_returns_opt_in_message():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeNoContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="tell me about hiv vct",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == [
        "The document does not explain this topic. I can provide a general explanation if you'd like, but it won't be from your medical records."
    ]


@pytest.mark.anyio
async def test_rag_ask_structured_refuses_without_evidence():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeNoContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response, structured = await rag.ask_structured(
        question="Summarize my records",
        patient_id=1,
    )

    assert structured is None
    assert response.answer == "I do not know from the available records."
    assert response.llm_response.finish_reason == "structured_no_evidence"


@pytest.mark.anyio
async def test_rag_ask_structured_latest_document_unavailable_message(monkeypatch):
    monkeypatch.setattr(settings, "llm_summary_best_effort_fallback", True)
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeNoContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response, structured = await rag.ask_structured(
        question="Summarize the most recent document using only explicit values.",
        patient_id=1,
    )

    assert structured is None
    assert response.answer == RAGService.LATEST_DOCUMENT_UNAVAILABLE
    assert (
        response.llm_response.finish_reason == "structured_latest_document_unavailable"
    )
    assert (
        rag.get_guardrail_counters().get("structured_latest_document_unavailable") == 1
    )


@pytest.mark.anyio
async def test_rag_ask_structured_refuses_on_invalid_json():
    llm = FakeInvalidStructuredLLMService()
    rag = RAGService(
        db=None,
        llm_service=llm,
        context_engine=FakeHighEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response, structured = await rag.ask_structured(
        question="what is my latest hemoglobin value",
        patient_id=1,
    )

    assert llm.call_count == 2
    assert structured is None
    assert response.answer == "I do not know from the available records."
    assert response.llm_response.finish_reason == "structured_invalid_json"


@pytest.mark.anyio
async def test_rag_stream_evidence_gating_blocks_missing_pulse_value():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeMissingPulseContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my pulse rate",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["The document does not record your pulse rate."]


class FakeLowEvidenceFactContextEngine:
    async def get_context(
        self,
        query,
        patient_id,
        max_tokens=4000,
        system_prompt=None,
        min_score=None,
        **_kwargs,
    ):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(
                full_context="Possible lab mention without clear match",
                total_chunks_used=1,
            ),
            ranked_results=[
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="document",
                        source_id=99,
                        content="Possible lab mention without clear match",
                    ),
                    final_score=0.1,
                )
            ],
            query_analysis=SimpleNamespace(
                intent=QueryIntent.VALUE,
                test_names=["hemoglobin"],
                medication_names=[],
            ),
        )


@pytest.mark.anyio
async def test_rag_strict_grounding_refuses_low_evidence_fact_query():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeLowEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    )

    assert response.answer == "I do not know from the available records."
    assert response.llm_response.finish_reason == "strict_grounding_no_evidence"
    assert rag.get_guardrail_counters().get("strict_grounding_no_evidence") == 1


@pytest.mark.anyio
async def test_rag_ask_latest_document_summary_refuses_with_specific_message(monkeypatch):
    monkeypatch.setattr(settings, "llm_summary_best_effort_fallback", True)
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="Summarize the most recent document using only explicit values.",
        patient_id=1,
    )

    assert response.answer == RAGService.LATEST_DOCUMENT_UNAVAILABLE
    assert response.llm_response.finish_reason == "latest_document_unavailable"
    assert rag.get_guardrail_counters().get("latest_document_unavailable") == 1


@pytest.mark.anyio
async def test_rag_stream_strict_grounding_refuses_low_evidence_fact_query():
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeLowEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["I do not know from the available records."]


@pytest.mark.anyio
async def test_rag_stream_latest_document_summary_refuses_with_specific_message(monkeypatch):
    monkeypatch.setattr(settings, "llm_summary_best_effort_fallback", True)
    rag = RAGService(
        db=None,
        llm_service=NeverCallLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="Summarize the most recent document using only explicit values.",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == [RAGService.LATEST_DOCUMENT_UNAVAILABLE]
    assert rag.get_guardrail_counters().get("latest_document_unavailable") == 1


@pytest.mark.anyio
async def test_rag_numeric_grounding_refuses_ungrounded_numeric_claim():
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingLLMService(),
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="summarize this report",
        patient_id=1,
    )

    assert response.answer == "I do not know from the available records."


@pytest.mark.anyio
async def test_rag_auto_attaches_numeric_citation_on_generated_answer():
    rag = RAGService(
        db=None,
        llm_service=FakeGroundedNumericLLMService(),
        context_engine=FakeHighEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    )

    assert "10.1 g/dL" in response.answer
    assert "(source: document#10)" in response.answer
    assert rag.get_guardrail_counters().get("numeric_citation_auto_attached") == 1


@pytest.mark.anyio
async def test_rag_stream_numeric_grounding_refuses_ungrounded_numeric_claim():
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingLLMService(),
        context_engine=FakeHighEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["I do not know from the available records."]


@pytest.mark.anyio
async def test_rag_stream_auto_attaches_numeric_citation_on_generated_answer():
    rag = RAGService(
        db=None,
        llm_service=FakeGroundedNumericLLMService(),
        context_engine=FakeHighEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["Your hemoglobin is 10.1 g/dL (source: document#10)."]
    assert rag.get_guardrail_counters().get("numeric_citation_auto_attached") == 1


@pytest.mark.anyio
async def test_rag_does_not_auto_attach_citation_when_source_match_is_ambiguous():
    rag = RAGService(
        db=None,
        llm_service=FakeGroundedNumericLLMService(),
        context_engine=FakeAmbiguousCitationContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    )

    assert response.answer == "Your hemoglobin is 10.1 g/dL."
    assert rag.get_guardrail_counters().get("numeric_citation_auto_attached") is None
    assert rag.get_guardrail_counters().get("numeric_citation_unmapped") == 1


@pytest.mark.anyio
async def test_rag_clinician_mode_refuses_uncited_numeric_claim():
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingLLMService(),
        context_engine=FakeClinicianContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
        system_prompt=RAGService.CLINICIAN_SYSTEM_PROMPT,
    )

    assert response.answer == "Your hemoglobin is 12.9 g/dL (source: document#88)."
    assert rag.get_guardrail_counters().get("numeric_citation_auto_attached") == 1


@pytest.mark.anyio
async def test_rag_patient_mode_can_require_citations(monkeypatch):
    monkeypatch.setattr(settings, "llm_require_numeric_citations", True)
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingLLMService(),
        context_engine=FakeNoSourceNumericContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(
        question="what is my hemoglobin level",
        patient_id=1,
    )

    assert response.answer == "I do not know from the available records."
    assert rag.get_guardrail_counters().get("citation_refusal") == 1


@pytest.mark.anyio
async def test_rag_stream_clinician_mode_refuses_uncited_numeric_claim():
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingLLMService(),
        context_engine=FakeClinicianContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
        system_prompt=RAGService.CLINICIAN_SYSTEM_PROMPT,
    ):
        chunks.append(chunk)

    assert chunks == ["Your hemoglobin is 12.9 g/dL (source: document#88)."]
    assert rag.get_guardrail_counters().get("numeric_citation_auto_attached") == 1


@pytest.mark.anyio
async def test_rag_stream_patient_mode_can_require_citations(monkeypatch):
    monkeypatch.setattr(settings, "llm_require_numeric_citations", True)
    rag = RAGService(
        db=None,
        llm_service=FakeHallucinatingNoStreamLLMService(),
        context_engine=FakeNoSourceNumericContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    chunks = []
    async for chunk in rag.stream_ask(
        question="what is my hemoglobin level",
        patient_id=1,
    ):
        chunks.append(chunk)

    assert chunks == ["I do not know from the available records."]
    assert rag.get_guardrail_counters().get("citation_refusal") == 1


@pytest.mark.anyio
async def test_rag_injects_few_shot_examples_for_factual_intents():
    llm = FakeLLMService()
    rag = RAGService(
        db=None,
        llm_service=llm,
        context_engine=FakeHighEvidenceFactContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    _ = await rag.ask(
        question="what is my latest hemoglobin value",
        patient_id=1,
    )

    assert llm.last_prompt is not None
    assert "Few-shot grounded behavior examples." in llm.last_prompt


def test_evidence_validator_blocks_missing_numeric_lab_value():
    validator = EvidenceValidator()

    can_answer, reason = validator.can_answer_from_context(
        question="what is my hemoglobin level",
        context_text="Hemoglobin was checked but the value is not legible.",
    )

    assert can_answer is False
    assert reason is not None
    assert "does not record your hemoglobin" in reason.lower()


def test_evidence_validator_missing_context_still_returns_specific_pulse_message():
    validator = EvidenceValidator()

    can_answer, reason = validator.can_answer_from_context(
        question="what is my pulse rate",
        context_text="",
    )

    assert can_answer is False
    assert reason is not None
    assert "does not record your pulse rate" in reason.lower()


def test_evidence_validator_classifies_my_questions_as_record_based():
    validator = EvidenceValidator()

    mode = validator.detect_question_mode("what is my pulse rate")

    assert mode == "RECORD_BASED"


def test_evidence_validator_detects_ungrounded_numeric_claims():
    validator = EvidenceValidator()
    response = "Your hemoglobin is 12.9 g/dL. HIV result is Negative."
    context = "Hemoglobin is 10.1 g/dL. HIV result is Negative."

    unsupported = validator.find_ungrounded_numeric_claims(response, context)

    assert len(unsupported) == 1
    assert "12.9" in unsupported[0]


def test_evidence_validator_enforce_numeric_grounding_keeps_grounded_text():
    validator = EvidenceValidator()
    response = "Your hemoglobin is 12.9 g/dL. HIV result is Negative."
    context = "Hemoglobin is 10.1 g/dL. HIV result is Negative."

    cleaned, unsupported = validator.enforce_numeric_grounding(
        response=response,
        context_text=context,
        refusal_message="I do not know from the available records.",
    )

    assert len(unsupported) == 1
    assert "12.9" not in cleaned
    assert "HIV result is Negative." in cleaned


def test_evidence_validator_detects_uncited_numeric_claims():
    validator = EvidenceValidator()
    response = "Hemoglobin: 12.9 g/dL. Pulse: 72 bpm (source: document#11)."

    uncited = validator.find_uncited_numeric_claims(response)

    assert len(uncited) == 1
    assert "Hemoglobin: 12.9 g/dL." in uncited[0]


def test_evidence_validator_requires_canonical_source_citation_format():
    validator = EvidenceValidator()
    response = "Pulse: 72 bpm (source: doc_id:11)."

    uncited = validator.find_uncited_numeric_claims(response)

    assert len(uncited) == 1
    assert "Pulse: 72 bpm (source: doc_id:11)." in uncited[0]


def test_evidence_validator_enforce_numeric_citations_refuses_if_all_uncited():
    validator = EvidenceValidator()
    response = "Hemoglobin: 12.9 g/dL."

    cleaned, uncited = validator.enforce_numeric_citations(
        response=response,
        refusal_message="Not in documents.",
    )

    assert len(uncited) == 1
    assert cleaned == "Not in documents."


def test_conversation_history_helpers():
    conversation = Conversation(conversation_id=None, patient_id=1)  # type: ignore[arg-type]
    conversation.add_message("user", "Hi")
    conversation.add_message("assistant", "Hello")

    history = conversation.to_history()
    assert history[0]["role"] == "user"
    assert conversation.get_last_n_turns(1)
