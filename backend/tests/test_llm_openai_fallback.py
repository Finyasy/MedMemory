from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

import app.services.llm.model as model_module
from app.config import settings
from app.services.llm.model import LLMResponse, LLMService


def test_openai_provider_settings(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory",
    )
    monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "medgemma")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_FALLBACK_ON_STATUSES", "[429,500]")

    config = importlib.import_module("app.config")
    importlib.reload(config)
    fresh_settings = config.Settings()

    assert fresh_settings.llm_primary_provider == "openai"
    assert fresh_settings.llm_fallback_provider == "medgemma"
    assert fresh_settings.openai_api_key == "sk-test"
    assert fresh_settings.openai_model == "gpt-test"
    assert fresh_settings.openai_fallback_on_statuses == [429, 500]


@pytest.mark.anyio
async def test_generate_uses_openai_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_fallback_provider", "medgemma", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "openai_model", "gpt-test", raising=False)

    service = LLMService(model_name="dummy", device="cpu")

    async def fake_post(payload):
        assert payload["model"] == "gpt-test"
        assert payload["input"] == "Hello"
        assert "Authorization" not in payload
        return {
            "status": "completed",
            "output_text": "Hi from OpenAI",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }

    monkeypatch.setattr(service, "_post_openai_response", fake_post)

    response = await service.generate("Hello")

    assert response.text == "Hi from OpenAI"
    assert response.provider == "openai"
    assert response.model_name == "gpt-test"
    assert response.tokens_input == 3
    assert response.tokens_generated == 4
    assert response.fallback_used is False


@pytest.mark.anyio
async def test_generate_falls_back_to_medgemma_on_openai_status(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_fallback_provider", "medgemma", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "openai_model", "gpt-test", raising=False)
    monkeypatch.setattr(settings, "openai_fallback_on_statuses", [429], raising=False)

    service = LLMService(model_name="local-medgemma", device="cpu")

    async def fake_openai(**_kwargs):
        raise model_module.OpenAIProviderUnavailableError("rate limit", status_code=429)

    async def fake_medgemma_text(**_kwargs):
        return LLMResponse(
            text="Hi from MedGemma",
            tokens_generated=2,
            tokens_input=1,
            generation_time_ms=5.0,
        )

    monkeypatch.setattr(service, "_generate_with_openai", fake_openai)
    monkeypatch.setattr(service, "_generate_with_medgemma_text", fake_medgemma_text)

    response = await service.generate("Hello")

    assert response.text == "Hi from MedGemma"
    assert response.provider == "medgemma"
    assert response.model_name == service.model_name
    assert response.fallback_used is True
    assert response.fallback_reason == "openai_http_429"


@pytest.mark.anyio
async def test_generate_does_not_fallback_on_unconfigured_openai_status(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_fallback_provider", "medgemma", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "openai_model", "gpt-test", raising=False)
    monkeypatch.setattr(settings, "openai_fallback_on_statuses", [429], raising=False)

    service = LLMService(model_name="local-medgemma", device="cpu")

    async def fake_openai(**_kwargs):
        raise model_module.OpenAIProviderUnavailableError("bad request", status_code=400)

    monkeypatch.setattr(service, "_generate_with_openai", fake_openai)

    with pytest.raises(model_module.OpenAIProviderUnavailableError):
        await service.generate("Hello")


@pytest.mark.anyio
async def test_generate_with_image_uses_openai_payload(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_fallback_provider", "medgemma", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "openai_model", "gpt-test", raising=False)

    service = LLMService(model_name="local-medgemma", device="cpu")
    service._processor = SimpleNamespace(tokenizer=SimpleNamespace())

    async def fake_post(payload):
        assert payload["model"] == "gpt-test"
        assert payload["instructions"] == "Be safe"
        content = payload["input"][0]["content"]
        assert content[0]["type"] == "input_image"
        assert content[0]["image_url"].startswith("data:image/")
        assert content[-1] == {"type": "input_text", "text": "Review"}
        return {
            "status": "completed",
            "output_text": "OpenAI image answer",
            "usage": {"input_tokens": 7, "output_tokens": 8},
        }

    monkeypatch.setattr(service, "_post_openai_response", fake_post)

    response = await service.generate_with_image(
        prompt="Review",
        image_bytes=b"not-real-image-but-openai-accepts-data-url",
        system_prompt="Be safe",
    )

    assert response.text == "OpenAI image answer"
    assert response.provider == "openai"
    assert response.tokens_input == 7
    assert response.tokens_generated == 8
