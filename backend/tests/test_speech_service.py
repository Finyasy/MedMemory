from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import speech_service


def test_internal_speech_service_requires_shared_key(monkeypatch):
    monkeypatch.setattr(
        speech_service.settings,
        "speech_service_internal_api_key",
        "secret-key",
    )
    client = TestClient(speech_service.app, raise_server_exceptions=False)

    response = client.get("/internal/v1/health")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid speech service credentials."


def test_internal_speech_service_synthesizes_with_valid_key(monkeypatch):
    class FakeService:
        async def synthesize(self, **kwargs):
            assert kwargs["output_language"] == "sw"
            assert kwargs["response_mode"] == "speech"
            return SimpleNamespace(
                audio_asset_id="speech/sw/service.wav",
                output_language="sw",
                response_mode="speech",
                audio_url="/api/v1/speech/assets/speech/sw/service.wav",
                audio_duration_ms=1120,
                speech_locale="sw-KE",
                model_name="facebook/mms-tts-swh",
            )

        async def readiness_status(self):
            return {"ok": True, "configured_source": "models/mms-tts-swh"}

    monkeypatch.setattr(
        speech_service.settings,
        "speech_service_internal_api_key",
        "secret-key",
    )
    monkeypatch.setattr(
        speech_service.SpeechSynthesisService,
        "get_instance",
        classmethod(lambda cls: FakeService()),
    )
    client = TestClient(speech_service.app, raise_server_exceptions=False)

    response = client.post(
        "/internal/v1/speech/synthesize",
        headers={"X-Speech-Service-Key": "secret-key"},
        json={
            "text": "Habari yako?",
            "output_language": "sw",
            "response_mode": "speech",
            "patient_id": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audio_asset_id"] == "speech/sw/service.wav"
    assert body["speech_locale"] == "sw-KE"
