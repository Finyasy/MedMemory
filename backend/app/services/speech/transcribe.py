"""English voice transcription service boundary."""

from __future__ import annotations

import asyncio
import functools
import logging
import math
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from fastapi import UploadFile

from app.config import settings
from app.services.speech.medasr_lm import (
    MedAsrLmDependencyError,
    build_medasr_lm_components,
    estimate_beam_confidence,
)
from app.services.speech.validators import (
    validate_audio_duration,
    validate_audio_payload_size,
    validate_transcript_confidence,
    validate_transcript_text,
)

logger = logging.getLogger("medmemory")
CTC_ARTIFACT_PATTERN = re.compile(r"</?s>|<epsilon>", re.IGNORECASE)
MULTISPACE_PATTERN = re.compile(r"\s+")
SPACE_BEFORE_PUNCTUATION_PATTERN = re.compile(r"\s+([,.;:!?])")


class SpeechServiceUnavailableError(RuntimeError):
    """Raised when a speech model is missing or unavailable."""


@dataclass(frozen=True)
class SpeechTranscriptionResult:
    transcript: str
    detected_language: str = "en"
    transcript_confidence: float | None = None
    duration_ms: int | None = None
    model_name: str | None = None


class SpeechTranscriptionService:
    """MedASR-backed English transcription service."""

    _instance: SpeechTranscriptionService | None = None

    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_path: Path | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.speech_transcription_model
        self.model_path = self._resolve_model_path(model_path or settings.speech_transcription_model_path)
        self.device = device or self._detect_device()
        self._pipeline: Any = None
        self._decoder_mode = "ctc"
        self._lm_path = self._resolve_lm_path(settings.speech_transcription_lm_path)
        self._pipeline_lock = asyncio.Lock()
        self._inference_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> SpeechTranscriptionService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_model_path(self, model_path: Path | None) -> Path | None:
        if not model_path:
            return None
        backend_dir = Path(__file__).resolve().parents[3]
        candidate = Path(model_path)
        if not candidate.is_absolute():
            candidate = (backend_dir / candidate).resolve()
        return candidate

    def _resolve_lm_path(self, lm_path: Path | None) -> Path | None:
        if lm_path:
            backend_dir = Path(__file__).resolve().parents[3]
            candidate = Path(lm_path)
            if not candidate.is_absolute():
                candidate = (backend_dir / candidate).resolve()
            return candidate
        if self.model_path:
            candidate = self.model_path / "lm_6.kenlm"
            return candidate if candidate.exists() else None
        return None

    def _detect_device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _model_source(self) -> str:
        if self.model_path:
            if not self.model_path.exists():
                raise SpeechServiceUnavailableError(
                    f"Speech transcription model path not found: {self.model_path}. "
                    "Download the MedASR checkpoint locally before enabling voice input."
                )
            return str(self.model_path)
        return self.model_name

    def _local_files_only(self) -> bool:
        return bool(
            settings.speech_require_local_assets
            or settings.hf_hub_offline
            or settings.transformers_offline
        )

    def _build_pipeline(self):
        try:
            from transformers import pipeline
        except ModuleNotFoundError as exc:
            missing_package = exc.name or "transformers"
            raise SpeechServiceUnavailableError(
                f"Missing required ML dependency '{missing_package}' for speech transcription. "
                "Install backend dependencies with: cd backend && uv sync."
            ) from exc

        if settings.hf_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
        if settings.transformers_offline or settings.speech_require_local_assets:
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        model_source = self._model_source()
        pipeline_kwargs: dict[str, Any] = {
            "task": "automatic-speech-recognition",
            "model": model_source,
            "tokenizer": model_source,
            "feature_extractor": model_source,
            "local_files_only": self._local_files_only(),
        }
        if settings.hf_token:
            pipeline_kwargs["token"] = settings.hf_token
        if settings.hf_cache_dir:
            pipeline_kwargs["cache_dir"] = str(settings.hf_cache_dir)

        model_kwargs: dict[str, Any] = {}
        if self.device == "cuda":
            pipeline_kwargs["device"] = 0
            model_kwargs["torch_dtype"] = torch.float16
        elif self.device == "cpu":
            pipeline_kwargs["device"] = -1
        else:
            model_kwargs["torch_dtype"] = torch.float32

        if model_kwargs:
            pipeline_kwargs["model_kwargs"] = model_kwargs

        self._lm_path = self._resolve_lm_path(settings.speech_transcription_lm_path)
        lm_decoder_enabled = (
            settings.speech_transcription_use_lm_decoder
            and self._lm_path is not None
            and self._lm_path.exists()
        )
        if lm_decoder_enabled:
            try:
                feature_extractor, decoder = build_medasr_lm_components(
                    model_source=model_source,
                    kenlm_model_path=self._lm_path,
                    local_files_only=self._local_files_only(),
                    cache_dir=(
                        str(settings.hf_cache_dir) if settings.hf_cache_dir else None
                    ),
                    token=settings.hf_token,
                    alpha=settings.speech_transcription_decoder_alpha,
                    beta=settings.speech_transcription_decoder_beta,
                )
                pipeline_kwargs["feature_extractor"] = feature_extractor
                pipeline_kwargs["decoder"] = decoder
                pipeline_kwargs.pop("tokenizer", None)
                self._decoder_mode = "ctc_with_lm"
            except MedAsrLmDependencyError as exc:
                logger.warning(
                    "Speech LM decoder unavailable; falling back to plain MedASR decode: %s",
                    exc,
                )
                self._decoder_mode = "ctc"
        else:
            self._decoder_mode = "ctc"

        logger.info(
            "Loading speech transcription model source=%s device=%s local_only=%s decoder=%s",
            model_source,
            self.device,
            pipeline_kwargs["local_files_only"],
            self._decoder_mode,
        )
        try:
            built_pipeline = pipeline(**pipeline_kwargs)
            self._decoder_mode = getattr(built_pipeline, "type", self._decoder_mode)
            return built_pipeline
        except OSError as exc:
            raise SpeechServiceUnavailableError(
                "Speech transcription model is not available locally. "
                "Download the configured MedASR checkpoint from Hugging Face first."
            ) from exc
        except Exception as exc:
            raise SpeechServiceUnavailableError(
                f"Failed to initialize speech transcription pipeline: {exc}"
            ) from exc

    async def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        async with self._pipeline_lock:
            if self._pipeline is None:
                loop = asyncio.get_running_loop()
                self._pipeline = await loop.run_in_executor(None, self._build_pipeline)
        return self._pipeline

    def health_status(self, *, error: str | None = None) -> dict[str, Any]:
        configured_source = str(self.model_path) if self.model_path else self.model_name
        local_path_exists = self.model_path.exists() if self.model_path else None
        return {
            "ok": self._pipeline is not None and error is None,
            "configured_source": configured_source,
            "device": self.device,
            "model_loaded": self._pipeline is not None,
            "local_only": self._local_files_only(),
            "local_path_exists": local_path_exists,
            "decoder_mode": self._decoder_mode,
            "lm_path": str(self._lm_path) if self._lm_path else None,
            "lm_path_exists": self._lm_path.exists() if self._lm_path else False,
            "error": error,
        }

    async def readiness_status(self) -> dict[str, Any]:
        error: str | None = None
        try:
            await self._get_pipeline()
        except RuntimeError as exc:
            error = str(exc)
        return self.health_status(error=error)

    def _probe_duration_ms(self, audio_bytes: bytes, suffix: str) -> int | None:
        ffprobe_path = shutil_which("ffprobe")
        if ffprobe_path is None:
            return None
        with tempfile.NamedTemporaryFile(suffix=suffix or ".audio", delete=True) as handle:
            handle.write(audio_bytes)
            handle.flush()
            command = [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                handle.name,
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    check=True,
                    text=True,
                    timeout=10,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return None
        try:
            seconds = float(completed.stdout.strip())
        except (TypeError, ValueError):
            return None
        if not math.isfinite(seconds) or seconds < 0:
            return None
        return int(seconds * 1000)

    def _decode_audio_array(self, audio_bytes: bytes, suffix: str) -> dict[str, Any]:
        ffmpeg_path = shutil_which("ffmpeg")
        if ffmpeg_path is None:
            raise SpeechServiceUnavailableError(
                "Speech transcription requires ffmpeg to decode uploaded audio formats."
            )
        command = [
            ffmpeg_path,
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                input=audio_bytes,
                capture_output=True,
                check=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpeechServiceUnavailableError(
                "Speech transcription timed out while decoding the uploaded audio."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore").strip()
            raise SpeechServiceUnavailableError(
                "Speech transcription could not decode the uploaded audio. "
                f"{stderr or 'ffmpeg failed to read the file.'}"
            ) from exc

        waveform = np.frombuffer(completed.stdout, dtype=np.float32)
        if waveform.size == 0:
            raise SpeechServiceUnavailableError(
                "Speech transcription decoded an empty audio stream."
            )
        return {"array": waveform, "sampling_rate": 16000}

    def _extract_confidence(self, payload: Any) -> float | None:
        if not isinstance(payload, dict):
            return None
        candidates: list[Any] = [
            payload.get("confidence"),
            payload.get("score"),
            payload.get("avg_logprob"),
        ]
        for value in candidates:
            if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
                return float(value)
        chunks = payload.get("chunks")
        if isinstance(chunks, list):
            scores = [
                float(chunk["score"])
                for chunk in chunks
                if isinstance(chunk, dict)
                and isinstance(chunk.get("score"), (int, float))
                and 0.0 <= float(chunk["score"]) <= 1.0
            ]
            if scores:
                return sum(scores) / len(scores)
        return None

    def _normalize_transcript(self, transcript: str) -> str:
        cleaned = CTC_ARTIFACT_PATTERN.sub(" ", transcript)
        cleaned = MULTISPACE_PATTERN.sub(" ", cleaned).strip()
        cleaned = SPACE_BEFORE_PUNCTUATION_PATTERN.sub(r"\1", cleaned)
        return validate_transcript_text(cleaned)

    def _extract_decoder_confidence(self, pipeline_instance: Any) -> float | None:
        decoder_candidates = [
            getattr(pipeline_instance, "decoder", None),
            getattr(getattr(pipeline_instance, "tokenizer", None), "decoder", None),
        ]
        seen_decoder_ids: set[int] = set()
        for decoder in decoder_candidates:
            if decoder is None:
                continue
            decoder_id = id(decoder)
            if decoder_id in seen_decoder_ids:
                continue
            seen_decoder_ids.add(decoder_id)
            beam_summaries = getattr(decoder, "last_beam_summaries", None)
            if beam_summaries:
                confidence = estimate_beam_confidence(beam_summaries)
                if confidence is not None:
                    return confidence
        return None

    def _run_pipeline(self, *, audio_input: Any) -> SpeechTranscriptionResult:
        pipeline_instance = self._pipeline
        if pipeline_instance is None:
            raise SpeechServiceUnavailableError(
                "Speech transcription pipeline is not loaded."
            )
        inference_kwargs: dict[str, Any] = {
            "chunk_length_s": settings.speech_transcription_chunk_length_seconds,
            "stride_length_s": settings.speech_transcription_stride_length_seconds,
        }
        if self._decoder_mode == "ctc_with_lm":
            inference_kwargs["decoder_kwargs"] = {
                "beam_width": settings.speech_transcription_decoder_beam_width,
            }
        try:
            payload = pipeline_instance(audio_input, **inference_kwargs)
        except TypeError:
            payload = pipeline_instance(audio_input)
        except Exception as exc:
            raise SpeechServiceUnavailableError(
                f"Speech transcription failed during inference: {exc}"
            ) from exc

        if isinstance(payload, dict):
            transcript = self._normalize_transcript(str(payload.get("text", "")))
            confidence = self._extract_confidence(payload)
        else:
            transcript = self._normalize_transcript(str(payload))
            confidence = None
        if confidence is None and self._decoder_mode == "ctc_with_lm":
            confidence = self._extract_decoder_confidence(pipeline_instance)

        validate_transcript_confidence(confidence)

        return SpeechTranscriptionResult(
            transcript=transcript,
            detected_language="en",
            transcript_confidence=confidence,
            model_name=self.model_name,
        )

    async def transcribe(
        self,
        *,
        audio: UploadFile,
        language: str,
        patient_id: int | None,
        clinician_mode: bool,
    ) -> SpeechTranscriptionResult:
        _ = language
        audio_bytes = await audio.read()
        validate_audio_payload_size(audio_bytes)
        duration_ms = self._probe_duration_ms(
            audio_bytes,
            suffix=Path(audio.filename or "clip.bin").suffix or ".bin",
        )
        validate_audio_duration(duration_ms)
        audio_input = self._decode_audio_array(
            audio_bytes,
            suffix=Path(audio.filename or "clip.bin").suffix or ".bin",
        )

        await self._get_pipeline()
        started = time.perf_counter()
        async with self._inference_lock:
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    functools.partial(self._run_pipeline, audio_input=audio_input),
                ),
                timeout=settings.speech_transcription_timeout_seconds,
            )
        total_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "speech.transcribe completed patient_id=%s clinician_mode=%s "
            "confidence=%s duration_ms=%s latency_ms=%s transcript_review_required=true",
            patient_id,
            clinician_mode,
            result.transcript_confidence,
            duration_ms,
            total_ms,
        )
        return SpeechTranscriptionResult(
            transcript=result.transcript,
            detected_language=result.detected_language,
            transcript_confidence=result.transcript_confidence,
            duration_ms=duration_ms,
            model_name=result.model_name,
        )


def shutil_which(binary: str) -> str | None:
    try:
        from shutil import which
    except ModuleNotFoundError:
        return None
    return which(binary)
