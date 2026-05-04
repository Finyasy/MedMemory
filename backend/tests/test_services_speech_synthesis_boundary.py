from types import SimpleNamespace

import httpx
import pytest

from app.services.speech.synthesis_boundary import SpeechSynthesisBoundary


@pytest.mark.anyio
async def test_in_process_boundary_delegates_to_local_service():
    class FakeLocalService:
        async def synthesize(self, **kwargs):
            assert kwargs["text"] == "Jambo"
            return SimpleNamespace(
                audio_asset_id="speech/sw/test.wav",
                output_language="sw",
                response_mode="speech",
                audio_url="/api/v1/speech/assets/speech/sw/test.wav",
                audio_duration_ms=950,
                speech_locale="sw-KE",
                model_name="facebook/mms-tts-swh",
            )

        async def readiness_status(self):
            return {"ok": True}

    boundary = SpeechSynthesisBoundary(
        backend_mode="in_process",
        local_service=FakeLocalService(),
    )

    result = await boundary.synthesize(
        text="Jambo",
        output_language="sw",
        response_mode="speech",
        patient_id=1,
        conversation_id=None,
        message_id=2,
    )

    assert result.audio_asset_id == "speech/sw/test.wav"
    assert result.audio_duration_ms == 950


@pytest.mark.anyio
async def test_http_boundary_calls_dedicated_service(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse(
                {
                    "audio_asset_id": "speech/sw/http.wav",
                    "output_language": "sw",
                    "response_mode": "both",
                    "audio_url": "/api/v1/speech/assets/speech/sw/http.wav",
                    "audio_duration_ms": 1040,
                    "speech_locale": "sw-KE",
                    "model_name": "facebook/mms-tts-swh",
                }
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    boundary = SpeechSynthesisBoundary(
        backend_mode="http",
        service_base_url="http://127.0.0.1:8010",
        service_timeout_seconds=12,
        service_api_key="internal-secret",
    )

    result = await boundary.synthesize(
        text="Habari yako",
        output_language="sw",
        response_mode="both",
        patient_id=9,
        conversation_id=None,
        message_id=4,
    )

    assert captured["url"] == "http://127.0.0.1:8010/internal/v1/speech/synthesize"
    assert captured["timeout"] == 12
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "X-Speech-Service-Key": "internal-secret",
    }
    assert captured["json"]["text"] == "Habari yako"
    assert result.audio_asset_id == "speech/sw/http.wav"


@pytest.mark.anyio
async def test_http_boundary_health_returns_failure_payload(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    boundary = SpeechSynthesisBoundary(
        backend_mode="http",
        service_base_url="http://127.0.0.1:8010",
    )

    status = await boundary.readiness_status()

    assert status["ok"] is False
    assert status["boundary_backend"] == "http"
    assert status["configured_source"] == "http://127.0.0.1:8010"
