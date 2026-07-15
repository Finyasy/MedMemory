from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import FileResponse

from app.api import speech as speech_api
from app.schemas.speech import SpeechSynthesisRequest


@pytest.mark.anyio
async def test_transcribe_rejects_non_english_language():
    with pytest.raises(HTTPException) as exc:
        await speech_api.transcribe_audio(
            audio=SimpleNamespace(filename="clip.wav", content_type="audio/wav"),
            patient_id=1,
            clinician_mode=False,
            language="sw",
        )

    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_transcribe_returns_structured_response(monkeypatch):
    class FakeService:
        async def transcribe(self, **_kwargs):
            return SimpleNamespace(
                transcript="Hello from speech",
                detected_language="en",
                transcript_confidence=0.93,
                duration_ms=1200,
                model_name="google/medasr",
            )

    monkeypatch.setattr(
        speech_api.SpeechTranscriptionService,
        "get_instance",
        classmethod(lambda cls: FakeService()),
    )

    response = await speech_api.transcribe_audio(
        audio=SimpleNamespace(filename="clip.wav", content_type="audio/wav"),
        patient_id=1,
        clinician_mode=False,
        language="en",
    )

    assert response.transcript == "Hello from speech"
    assert response.input_mode == "voice"
    assert response.model_name == "google/medasr"


@pytest.mark.anyio
async def test_synthesize_returns_structured_response(monkeypatch):
    class FakeService:
        async def synthesize(self, **_kwargs):
            return SimpleNamespace(
                audio_asset_id="speech/sw/test.wav",
                output_language="sw",
                response_mode="speech",
                audio_url="/audio/speech/sw/test.wav",
                audio_duration_ms=980,
                speech_locale="sw-KE",
                model_name="facebook/mms-tts-swh",
            )

    monkeypatch.setattr(
        speech_api.SpeechSynthesisBoundary,
        "get_instance",
        classmethod(lambda cls: FakeService()),
    )

    response = await speech_api.synthesize_speech(
        SpeechSynthesisRequest(text="Habari yako?", output_language="sw")
    )

    assert response.audio_asset_id == "speech/sw/test.wav"
    assert response.output_language == "sw"
    assert response.speech_locale == "sw-KE"


@pytest.mark.anyio
async def test_speech_health_reports_readiness(monkeypatch):
    class FakeTranscriptionService:
        async def readiness_status(self):
            return {"ok": True, "model_loaded": True, "configured_source": "models/medasr"}

    class FakeSynthesisBoundary:
        async def readiness_status(self):
            return {
                "ok": True,
                "model_loaded": True,
                "configured_source": "models/mms-tts-swh",
                "boundary_backend": "in_process",
            }

    monkeypatch.setattr(
        speech_api.SpeechTranscriptionService,
        "get_instance",
        classmethod(lambda cls: FakeTranscriptionService()),
    )
    monkeypatch.setattr(
        speech_api.SpeechSynthesisBoundary,
        "get_instance",
        classmethod(lambda cls: FakeSynthesisBoundary()),
    )

    response = await speech_api.speech_health()

    assert response["transcription"]["ok"] is True
    assert response["transcription"]["configured_source"] == "models/medasr"
    assert response["synthesis"]["configured_source"] == "models/mms-tts-swh"
    assert response["synthesis"]["boundary_backend"] == "in_process"


@pytest.mark.anyio
async def test_get_speech_asset_checks_patient_access(monkeypatch, tmp_path):
    audio_path = tmp_path / "reply.wav"
    audio_path.write_bytes(b"RIFFdemo")

    class FakeStorageService:
        async def read_generated_audio(self, **_kwargs):
            return SimpleNamespace(
                absolute_path=audio_path,
                mime_type="audio/wav",
                metadata={"patient_id": 11},
            )

    authorized_calls: list[int] = []

    async def fake_get_authorized_patient(*, patient_id, **_kwargs):
        authorized_calls.append(patient_id)
        return SimpleNamespace(id=patient_id)

    monkeypatch.setattr(
        speech_api.SpeechStorageService,
        "get_instance",
        classmethod(lambda cls: FakeStorageService()),
    )
    monkeypatch.setattr(speech_api, "get_authorized_patient", fake_get_authorized_patient)

    response = await speech_api.get_speech_asset(
        asset_id="speech/sw/patient-11/demo.wav",
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=7),
    )

    assert isinstance(response, FileResponse)
    assert authorized_calls == [11]
