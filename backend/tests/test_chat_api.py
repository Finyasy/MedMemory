from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api import chat as chat_api
from app.schemas.chat import ChatRequest, ConversationCreate


class FakeRagResponse:
    def __init__(self):
        self.answer = "Answer"
        self.conversation_id = UUID("11111111-1111-1111-1111-111111111111")
        self.message_id = 1
        self.num_sources = 1
        self.sources_summary = [
            {"source_type": "lab_result", "source_id": 1, "relevance": 0.8}
        ]
        self.llm_response = SimpleNamespace(
            tokens_input=10,
            tokens_generated=20,
            total_tokens=30,
        )
        self.context_time_ms = 5.0
        self.generation_time_ms = 15.0
        self.total_time_ms = 20.0


class FakeConversation:
    def __init__(self, patient_id=1):
        self.conversation_id = UUID("22222222-2222-2222-2222-222222222222")
        self.patient_id = patient_id
        self.title = "Test"
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.messages = [
            SimpleNamespace(
                role="assistant",
                content="Structured answer",
                timestamp=datetime.now(UTC),
                message_id=9,
                structured_data={"overview": "Structured history card"},
            )
        ]


class FakeConversationManager:
    def __init__(self, *_args, **_kwargs):
        pass

    async def create_conversation(self, patient_id, title=None):
        return FakeConversation(patient_id=patient_id)

    async def get_conversation(self, _conversation_id):
        return FakeConversation(patient_id=1)

    async def list_conversations(self, _patient_id, _limit):
        return [FakeConversation(patient_id=_patient_id)]

    async def delete_conversation(self, _conversation_id):
        return True

    async def update_title(self, _conversation_id, _title):
        return True


class FakeStructuredPayload:
    def model_dump(self):
        return {
            "overview": "Structured overview",
            "key_results": [],
            "medications": [],
            "vital_signs": {},
            "follow_ups": [],
            "concerns": [],
            "what_changed": [],
            "why_it_matters": [],
            "suggested_next_discussion_points": [],
            "section_sources": {},
            "source_document_id": None,
            "extraction_date": None,
        }


class FakeMultilingual:
    def resolve_context(
        self,
        *,
        input_language=None,
        output_language=None,
        preferred_language=None,
        clinician_mode=False,
    ):
        _ = preferred_language
        resolved_input = "en" if clinician_mode else (input_language or "en")
        resolved_output = "en" if clinician_mode else (output_language or resolved_input)
        return SimpleNamespace(
            input_language=resolved_input,
            output_language=resolved_output,
            detected_language=resolved_input,
            translation_applied=resolved_input != "en" or resolved_output != "en",
            speech_locale="sw-KE" if resolved_output == "sw" else "en-US",
        )

    async def translate_question_to_english(self, question, *, source_language):
        return f"EN::{question}" if source_language != "en" else question

    async def translate_answer_from_english(self, answer, *, target_language):
        return f"{target_language.upper()}::{answer}" if target_language != "en" else answer

    async def translate_structured_payload(self, payload, *, target_language):
        if payload is None or target_language == "en":
            return payload
        translated = dict(payload)
        translated["overview"] = f"{target_language.upper()}::{payload['overview']}"
        return translated

    @staticmethod
    def split_for_streaming(text, max_chars=180):
        _ = max_chars
        return [text]


@pytest.mark.anyio
async def test_ask_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(chat_api, "get_authorized_patient", _deny)

    with pytest.raises(HTTPException) as exc:
        await chat_api.ask_question(
            request=ChatRequest(question="Hi", patient_id=99),
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_ask_returns_rag_response(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            pass

        async def ask(self, **_kwargs):
            return FakeRagResponse()

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    response = await chat_api.ask_question(
        request=ChatRequest(question="Hi", patient_id=1),
        structured=False,
        clinician_mode=False,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    assert response.answer == "Answer"
    assert response.num_sources == 1
    assert response.sources[0].source_type == "lab_result"


@pytest.mark.anyio
async def test_ask_returns_translated_answer_metadata(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return SimpleNamespace(preferred_language="sw")

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            pass

        async def ask(self, **kwargs):
            assert kwargs["question"] == "EN::Habari"
            return FakeRagResponse()

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)
    monkeypatch.setattr(chat_api, "MultilingualChatService", FakeMultilingual)

    response = await chat_api.ask_question(
        request=ChatRequest(
            question="Habari",
            patient_id=1,
            input_language="sw",
            output_language="sw",
        ),
        structured=False,
        clinician_mode=False,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    assert response.answer == "SW::Answer"
    assert response.detected_language == "sw"
    assert response.output_language == "sw"
    assert response.translation_applied is True
    assert response.translated_question == "EN::Habari"
    assert response.speech_locale == "sw-KE"


@pytest.mark.anyio
async def test_ask_clinician_mode_passes_clinician_system_prompt(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    captured: dict = {}

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician-prompt"

        def __init__(self, *_args, **_kwargs):
            pass

        async def ask(self, **kwargs):
            captured.update(kwargs)
            return FakeRagResponse()

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    _ = await chat_api.ask_question(
        request=ChatRequest(question="Clinician request", patient_id=1),
        structured=False,
        clinician_mode=True,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    assert captured["system_prompt"] == FakeRAG.CLINICIAN_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_ask_structured_returns_structured_data(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            pass

        async def ask_structured(self, **_kwargs):
            return FakeRagResponse(), FakeStructuredPayload()

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    response = await chat_api.ask_question(
        request=ChatRequest(question="Structured please", patient_id=1),
        structured=True,
        clinician_mode=False,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    assert response.structured_data is not None
    assert response.structured_data.overview == "Structured overview"
    assert response.num_sources == 1


@pytest.mark.anyio
async def test_stream_denies_unowned_patient(monkeypatch):
    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(chat_api, "get_authorized_patient", _deny)

    with pytest.raises(HTTPException) as exc:
        await chat_api.stream_ask(
            question="Hello",
            patient_id=123,
            conversation_id=None,
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_stream_completion_emits_sources_metadata(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            self._metadata = {
                "num_sources": 2,
                "sources_summary": [
                    {"source_type": "lab_result", "source_id": 44, "relevance": 0.91}
                ],
                "structured_data": {"overview": "Structured overview"},
            }

        async def stream_ask(self, **_kwargs):
            yield "A"
            yield "B"

        def get_last_stream_metadata(self):
            return self._metadata

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "ConversationManager", FakeConversationManager)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    response = await chat_api.stream_ask(
        question="Hello",
        patient_id=1,
        conversation_id=None,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    payloads = []
    async for raw in response.body_iterator:
        chunk = raw if isinstance(raw, str) else raw.decode()
        events = [item.strip() for item in chunk.split("\n\n") if item.strip()]
        for event in events:
            assert event.startswith("data:")
            payloads.append(json.loads(event.replace("data:", "", 1).strip()))

    assert len(payloads) >= 3
    assert payloads[0]["chunk"] == "A"
    assert payloads[1]["chunk"] == "B"
    assert payloads[-1]["is_complete"] is True
    assert payloads[-1]["num_sources"] == 2
    assert payloads[-1]["sources"][0]["source_type"] == "lab_result"
    assert payloads[-1]["sources"][0]["source_id"] == 44
    assert payloads[-1]["structured_data"]["overview"] == "Structured overview"


@pytest.mark.anyio
async def test_stream_non_english_emits_translated_metadata(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return SimpleNamespace(preferred_language="sw")

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            self._metadata = {
                "num_sources": 1,
                "sources_summary": [
                    {"source_type": "lab_result", "source_id": 44, "relevance": 0.91}
                ],
                "structured_data": None,
            }

        async def ask(self, **kwargs):
            assert kwargs["question"] == "EN::Habari"
            return FakeRagResponse()

        def get_last_stream_metadata(self):
            return self._metadata

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "ConversationManager", FakeConversationManager)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)
    monkeypatch.setattr(chat_api, "MultilingualChatService", FakeMultilingual)

    response = await chat_api.stream_ask(
        question="Habari",
        patient_id=1,
        conversation_id=None,
        input_language="sw",
        output_language="sw",
        clinician_mode=False,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    payloads = []
    async for raw in response.body_iterator:
        chunk = raw if isinstance(raw, str) else raw.decode()
        events = [item.strip() for item in chunk.split("\n\n") if item.strip()]
        for event in events:
            payloads.append(json.loads(event.replace("data:", "", 1).strip()))

    assert payloads[0]["chunk"] == "SW::Answer"
    assert payloads[-1]["is_complete"] is True
    assert payloads[-1]["output_language"] == "sw"
    assert payloads[-1]["translated_question"] == "EN::Habari"
    assert payloads[-1]["speech_locale"] == "sw-KE"


@pytest.mark.anyio
async def test_stream_non_english_emits_first_chunk_before_speech_finishes(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return SimpleNamespace(preferred_language="sw")

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician"

        def __init__(self, *_args, **_kwargs):
            self._metadata = {
                "num_sources": 1,
                "sources_summary": [
                    {"source_type": "lab_result", "source_id": 44, "relevance": 0.91}
                ],
                "structured_data": None,
            }

        async def ask(self, **_kwargs):
            return FakeRagResponse()

        def get_last_stream_metadata(self):
            return self._metadata

    async def fake_attach_speech(**_kwargs):
        await asyncio.sleep(0.2)
        return {
            "response_mode": "both",
            "audio_asset_id": "speech/sw/test.wav",
            "audio_url": "/api/v1/speech/assets/speech/sw/test.wav",
            "audio_duration_ms": 1200,
        }

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "ConversationManager", FakeConversationManager)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)
    monkeypatch.setattr(chat_api, "MultilingualChatService", FakeMultilingual)
    monkeypatch.setattr(chat_api, "_maybe_attach_speech", fake_attach_speech)

    response = await chat_api.stream_ask(
        question="Habari",
        patient_id=1,
        conversation_id=None,
        input_language="sw",
        output_language="sw",
        response_mode="both",
        clinician_mode=False,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    iterator = response.body_iterator.__aiter__()
    start = time.monotonic()
    first_raw = await anext(iterator)
    elapsed = time.monotonic() - start
    first_payload = json.loads((first_raw if isinstance(first_raw, str) else first_raw.decode()).replace("data:", "", 1).strip())

    assert elapsed < 0.15
    assert first_payload["chunk"] == "SW::Answer"

    remaining_payloads = [first_payload]
    async for raw in iterator:
        chunk = raw if isinstance(raw, str) else raw.decode()
        events = [item.strip() for item in chunk.split("\n\n") if item.strip()]
        for event in events:
            remaining_payloads.append(json.loads(event.replace("data:", "", 1).strip()))

    assert remaining_payloads[-1]["audio_asset_id"] == "speech/sw/test.wav"


@pytest.mark.anyio
async def test_stream_clinician_mode_passes_clinician_system_prompt(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    captured: dict = {}

    class FakeRAG:
        CLINICIAN_SYSTEM_PROMPT = "clinician-prompt"

        def __init__(self, *_args, **_kwargs):
            self._metadata = {
                "num_sources": 0,
                "sources_summary": [],
                "structured_data": None,
            }

        async def stream_ask(self, **kwargs):
            captured.update(kwargs)
            yield "one chunk"

        def get_last_stream_metadata(self):
            return self._metadata

    monkeypatch.setattr(chat_api, "get_authorized_patient", _allow)
    monkeypatch.setattr(chat_api, "ConversationManager", FakeConversationManager)
    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    response = await chat_api.stream_ask(
        question="Hello clinician",
        patient_id=1,
        conversation_id=None,
        clinician_mode=True,
        db=None,
        current_user=SimpleNamespace(id=1),
    )

    async for _ in response.body_iterator:
        pass

    assert captured["system_prompt"] == FakeRAG.CLINICIAN_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_vision_requires_image(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat_api, "get_patient_for_user", _allow)

    class FakeUpload:
        content_type = "text/plain"

        async def read(self):
            return b"not-image"

    with pytest.raises(HTTPException) as exc:
        await chat_api.ask_with_image(
            prompt="Check",
            patient_id=1,
            image=FakeUpload(),
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_volume_requires_min_slices(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat_api, "get_patient_for_user", _allow)

    class FakeUpload:
        filename = "slice1.png"
        content_type = "image/png"

        async def read(self):
            return b"slice"

    with pytest.raises(HTTPException) as exc:
        await chat_api.ask_with_volume(
            prompt="Check",
            patient_id=1,
            slices=[FakeUpload(), FakeUpload()],
            sample_count=5,
            tile_size=256,
            modality="CT",
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_conversation_crud_happy_path(monkeypatch):
    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat_api, "get_patient_for_user", _allow)
    monkeypatch.setattr(chat_api, "ConversationManager", FakeConversationManager)

    created = await chat_api.create_conversation(
        request=ConversationCreate(patient_id=1, title="Check-in"),
        db=None,
        current_user=SimpleNamespace(id=1),
    )
    assert created.patient_id == 1

    fetched = await chat_api.get_conversation(
        conversation_id=UUID("22222222-2222-2222-2222-222222222222"),
        db=None,
        current_user=SimpleNamespace(id=1),
    )
    assert fetched.patient_id == 1
    assert fetched.messages[0].structured_data == {"overview": "Structured history card"}

    listed = await chat_api.list_conversations(
        patient_id=1,
        limit=10,
        db=None,
        current_user=SimpleNamespace(id=1),
    )
    assert len(listed) == 1
