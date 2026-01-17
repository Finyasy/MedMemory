from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.llm.model import LLMResponse, LLMService
from app.services.llm.rag import RAGService
from app.services.llm.conversation import Conversation


def test_llm_response_total_tokens():
    response = LLMResponse(text="hi", tokens_generated=2, tokens_input=3, generation_time_ms=1.0)
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
        self._conversation.add_message(role, content)
        return SimpleNamespace(message_id=1)


@dataclass
class FakeContextResult:
    prompt: str
    synthesized_context: SimpleNamespace
    ranked_results: list


class FakeContextEngine:
    async def get_context(self, query, patient_id, max_tokens=4000, system_prompt=None):
        return FakeContextResult(
            prompt="PROMPT",
            synthesized_context=SimpleNamespace(full_context="CTX", total_chunks_used=1),
            ranked_results=[SimpleNamespace(result=SimpleNamespace(source_type="lab", source_id=1), final_score=0.9)],
        )


class FakeLLMService:
    def __init__(self):
        self.last_history = None

    async def generate(self, prompt, max_new_tokens=512, conversation_history=None):
        self.last_history = conversation_history
        return LLMResponse(text="Answer", tokens_generated=2, tokens_input=3, generation_time_ms=1.0)

    async def stream_generate(self, prompt, system_prompt=None):
        for chunk in ["A", "B"]:
            yield chunk


@pytest.mark.anyio
async def test_rag_service_ask():
    llm = FakeLLMService()
    rag = RAGService(
        db=None,
        llm_service=llm,
        context_engine=FakeContextEngine(),
        conversation_manager=FakeConversationManager(),
    )

    response = await rag.ask(question="Q", patient_id=1)

    assert response.answer == "Answer"
    assert response.num_sources == 1
    assert llm.last_history
    assert llm.last_history[-1]["role"] == "user"


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


def test_conversation_history_helpers():
    conversation = Conversation(conversation_id=None, patient_id=1)  # type: ignore[arg-type]
    conversation.add_message("user", "Hi")
    conversation.add_message("assistant", "Hello")

    history = conversation.to_history()
    assert history[0]["role"] == "user"
    assert conversation.get_last_n_turns(1)
