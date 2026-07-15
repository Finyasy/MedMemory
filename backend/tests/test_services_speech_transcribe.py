from __future__ import annotations

import math
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

import pytest

import app.services.speech.transcribe as transcribe_module
from app.services.speech.medasr_lm import BeamScoreSummary
from app.services.speech.transcribe import (
    SpeechServiceUnavailableError,
    SpeechTranscriptionService,
)


class FakeUploadFile:
    def __init__(self, payload: bytes, *, filename: str = "clip.webm", content_type: str = "audio/webm"):
        self._payload = payload
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._payload


def test_build_pipeline_requires_local_model_path_when_configured():
    service = SpeechTranscriptionService(model_path=Path("missing-medasr"))

    with pytest.raises(SpeechServiceUnavailableError, match="model path not found"):
        service._build_pipeline()


@pytest.mark.anyio
async def test_transcribe_returns_structured_result(monkeypatch):
    service = SpeechTranscriptionService(model_name="google/medasr")
    service._pipeline = lambda _audio, **_kwargs: {
        "text": " Hello from speech ",
        "confidence": 0.91,
    }

    async def _fake_get_pipeline():
        return service._pipeline

    monkeypatch.setattr(service, "_get_pipeline", _fake_get_pipeline)
    monkeypatch.setattr(service, "_probe_duration_ms", lambda *_args, **_kwargs: 1250)
    monkeypatch.setattr(
        service,
        "_decode_audio_array",
        lambda *_args, **_kwargs: {"array": [0.0, 0.1], "sampling_rate": 16000},
    )

    result = await service.transcribe(
        audio=FakeUploadFile(b"audio-bytes"),
        language="en",
        patient_id=7,
        clinician_mode=False,
    )

    assert result.transcript == "Hello from speech"
    assert result.transcript_confidence == pytest.approx(0.91)
    assert result.duration_ms == 1250
    assert result.model_name == "google/medasr"


@pytest.mark.anyio
async def test_transcribe_rejects_low_confidence(monkeypatch):
    service = SpeechTranscriptionService(model_name="google/medasr")
    service._pipeline = lambda _audio, **_kwargs: {
        "text": "uncertain result",
        "confidence": 0.12,
    }

    async def _fake_get_pipeline():
        return service._pipeline

    monkeypatch.setattr(service, "_get_pipeline", _fake_get_pipeline)
    monkeypatch.setattr(service, "_probe_duration_ms", lambda *_args, **_kwargs: 900)
    monkeypatch.setattr(
        service,
        "_decode_audio_array",
        lambda *_args, **_kwargs: {"array": [0.0, 0.1], "sampling_rate": 16000},
    )

    with pytest.raises(ValueError, match="confidence is too low"):
        await service.transcribe(
            audio=FakeUploadFile(b"audio-bytes"),
            language="en",
            patient_id=None,
            clinician_mode=True,
        )


@pytest.mark.anyio
async def test_transcribe_does_not_send_invalid_ctc_timestamp_flag(monkeypatch):
    captured_kwargs: dict[str, object] = {}
    service = SpeechTranscriptionService(model_name="google/medasr")

    def fake_pipeline(_audio, **kwargs):
        captured_kwargs.update(kwargs)
        return {"text": "latest hemoglobin", "confidence": 0.88}

    service._pipeline = fake_pipeline

    async def _fake_get_pipeline():
        return service._pipeline

    monkeypatch.setattr(service, "_get_pipeline", _fake_get_pipeline)
    monkeypatch.setattr(service, "_probe_duration_ms", lambda *_args, **_kwargs: 1000)
    monkeypatch.setattr(
        service,
        "_decode_audio_array",
        lambda *_args, **_kwargs: {"array": [0.0, 0.1], "sampling_rate": 16000},
    )

    result = await service.transcribe(
        audio=FakeUploadFile(b"audio-bytes"),
        language="en",
        patient_id=3,
        clinician_mode=False,
    )

    assert result.transcript == "latest hemoglobin"
    assert "return_timestamps" not in captured_kwargs


def test_run_pipeline_passes_lm_decoder_kwargs():
    captured_kwargs: dict[str, object] = {}
    service = SpeechTranscriptionService(model_name="google/medasr")
    service._decoder_mode = "ctc_with_lm"

    def fake_pipeline(_audio, **kwargs):
        captured_kwargs.update(kwargs)
        return {"text": "latest hemoglobin"}

    service._pipeline = fake_pipeline

    result = service._run_pipeline(audio_input={"array": [0.0], "sampling_rate": 16000})

    assert result.transcript == "latest hemoglobin"
    assert captured_kwargs["decoder_kwargs"] == {"beam_width": 8}
    assert captured_kwargs["stride_length_s"] == 2


def test_run_pipeline_uses_lm_beam_confidence_when_payload_omits_one():
    service = SpeechTranscriptionService(model_name="google/medasr")
    service._decoder_mode = "ctc_with_lm"
    beam_summaries = (
        BeamScoreSummary(
            text="latest hemoglobin result",
            logit_score=-4.2,
            lm_score=-12.0,
        ),
        BeamScoreSummary(
            text="latest hemoglobin results",
            logit_score=-4.8,
            lm_score=-13.8,
        ),
        BeamScoreSummary(
            text="latest hemoglobin",
            logit_score=-5.0,
            lm_score=-15.5,
        ),
    )

    class FakePipeline:
        decoder = SimpleNamespace(last_beam_summaries=beam_summaries)

        def __call__(self, _audio, **_kwargs):
            return {"text": "latest hemoglobin result"}

    service._pipeline = FakePipeline()

    result = service._run_pipeline(audio_input={"array": [0.0], "sampling_rate": 16000})

    assert result.transcript == "latest hemoglobin result"
    assert result.transcript_confidence == pytest.approx(0.8364727049)


def test_run_pipeline_prefers_payload_confidence_over_decoder_beams():
    service = SpeechTranscriptionService(model_name="google/medasr")
    service._decoder_mode = "ctc_with_lm"
    beam_summaries = (
        BeamScoreSummary(
            text="latest hemoglobin result",
            logit_score=-4.2,
            lm_score=-12.0,
        ),
        BeamScoreSummary(
            text="latest hemoglobin results",
            logit_score=-4.8,
            lm_score=-13.8,
        ),
    )

    class FakePipeline:
        decoder = SimpleNamespace(last_beam_summaries=beam_summaries)

        def __call__(self, _audio, **_kwargs):
            return {"text": "latest hemoglobin result", "confidence": 0.66}

    service._pipeline = FakePipeline()

    result = service._run_pipeline(audio_input={"array": [0.0], "sampling_rate": 16000})

    assert result.transcript_confidence == pytest.approx(0.66)


def test_build_pipeline_enables_lm_decoder_when_available(monkeypatch, tmp_path):
    service = SpeechTranscriptionService(model_path=tmp_path)
    (tmp_path / "lm_6.kenlm").write_text("lm")

    class FakePipeline:
        type = "ctc_with_lm"

    captured_kwargs: dict[str, object] = {}

    def fake_pipeline(**kwargs):
        captured_kwargs.update(kwargs)
        return FakePipeline()

    monkeypatch.setattr(
        transcribe_module,
        "build_medasr_lm_components",
        lambda **_kwargs: ("feature-extractor", "decoder"),
    )
    monkeypatch.setattr("transformers.pipeline", fake_pipeline)

    pipeline_instance = service._build_pipeline()

    assert isinstance(pipeline_instance, FakePipeline)
    assert captured_kwargs["feature_extractor"] == "feature-extractor"
    assert captured_kwargs["decoder"] == "decoder"
    assert service._decoder_mode == "ctc_with_lm"


def test_build_pipeline_falls_back_when_lm_decoder_is_unavailable(monkeypatch, tmp_path):
    service = SpeechTranscriptionService(model_path=tmp_path)
    (tmp_path / "lm_6.kenlm").write_text("lm")

    class FakePipeline:
        type = "ctc"

    captured_kwargs: dict[str, object] = {}

    def fake_pipeline(**kwargs):
        captured_kwargs.update(kwargs)
        return FakePipeline()

    def raise_missing_decoder(**_kwargs):
        raise transcribe_module.MedAsrLmDependencyError("missing optional deps")

    monkeypatch.setattr(
        transcribe_module,
        "build_medasr_lm_components",
        raise_missing_decoder,
    )
    monkeypatch.setattr("transformers.pipeline", fake_pipeline)

    pipeline_instance = service._build_pipeline()

    assert isinstance(pipeline_instance, FakePipeline)
    assert "decoder" not in captured_kwargs
    assert service._decoder_mode == "ctc"


def test_decode_audio_array_returns_waveform_for_ffmpeg_ready_clip():
    service = SpeechTranscriptionService(model_name="google/medasr")
    sample_rate = 16000
    duration_seconds = 0.25
    frame_count = int(sample_rate * duration_seconds)
    with NamedTemporaryFile(suffix=".wav") as handle:
        with wave.open(handle.name, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = bytearray()
            for index in range(frame_count):
                amplitude = int(
                    32767 * math.sin(2 * math.pi * 440 * (index / sample_rate))
                )
                frames.extend(amplitude.to_bytes(2, byteorder="little", signed=True))
            wav_file.writeframes(bytes(frames))
        payload = Path(handle.name).read_bytes()

        decoded = service._decode_audio_array(payload, ".wav")

        assert decoded["sampling_rate"] == 16000
        assert len(decoded["array"]) > 0


def test_normalize_transcript_removes_ctc_artifacts():
    service = SpeechTranscriptionService(model_name="google/medasr")

    normalized = service._normalize_transcript(
        " <epsilon> What are the latest hemoglobin results ? </s> "
    )

    assert normalized == "What are the latest hemoglobin results?"
