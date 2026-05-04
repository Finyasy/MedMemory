"""Swahili speech synthesis service boundary."""

from __future__ import annotations

import asyncio
import functools
import hashlib
import io
import logging
import os
import re
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.config import settings
from app.services.speech.storage import SpeechStorageService

logger = logging.getLogger("medmemory")
MULTISPACE_PATTERN = re.compile(r"\s+")


class SpeechSynthesisUnavailableError(RuntimeError):
    """Raised when the Swahili TTS runtime is missing or unavailable."""


@dataclass(frozen=True)
class _SpeechSynthesisRuntime:
    tokenizer: Any
    model: Any
    sampling_rate: int


@dataclass(frozen=True)
class SpeechSynthesisResult:
    audio_asset_id: str
    output_language: str = "sw"
    response_mode: str = "speech"
    audio_url: str | None = None
    audio_duration_ms: int | None = None
    speech_locale: str | None = None
    model_name: str | None = None


class SpeechSynthesisService:
    """Swahili MMS-TTS service with local asset caching."""

    _instance: SpeechSynthesisService | None = None

    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_path: Path | None = None,
        device: str | None = None,
        storage: SpeechStorageService | None = None,
    ) -> None:
        self.model_name = model_name or settings.speech_synthesis_model
        self.model_path = self._resolve_model_path(
            model_path or settings.speech_synthesis_model_path
        )
        self.device = device or self._detect_device()
        self.storage = storage or SpeechStorageService.get_instance()
        self._runtime: _SpeechSynthesisRuntime | None = None
        self._runtime_lock = asyncio.Lock()
        self._inference_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> SpeechSynthesisService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_model_path(self, model_path: Path | None) -> Path | None:
        backend_dir = Path(__file__).resolve().parents[3]
        if not model_path:
            repo_slug = self.model_name.rsplit("/", 1)[-1]
            candidate = (backend_dir / "models" / repo_slug).resolve()
            return candidate if candidate.exists() else None
        candidate = Path(model_path)
        if not candidate.is_absolute():
            candidate = (backend_dir / candidate).resolve()
        return candidate

    def _detect_device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _local_files_only(self) -> bool:
        return bool(
            settings.speech_require_local_assets
            or settings.hf_hub_offline
            or settings.transformers_offline
        )

    def _model_source(self) -> str:
        if self.model_path:
            if not self.model_path.exists():
                raise SpeechSynthesisUnavailableError(
                    f"Speech synthesis model path not found: {self.model_path}. "
                    "Download the Swahili TTS checkpoint locally before enabling speech output."
                )
            return str(self.model_path)
        return self.model_name

    def _build_runtime(self) -> _SpeechSynthesisRuntime:
        try:
            from transformers import AutoTokenizer, VitsModel
        except ModuleNotFoundError as exc:
            missing_package = exc.name or "transformers"
            raise SpeechSynthesisUnavailableError(
                f"Missing required ML dependency '{missing_package}' for speech synthesis. "
                "Install backend dependencies with: cd backend && uv sync."
            ) from exc

        if settings.hf_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
        if settings.transformers_offline or settings.speech_require_local_assets:
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        model_source = self._model_source()
        load_kwargs: dict[str, Any] = {"local_files_only": self._local_files_only()}
        if settings.hf_token:
            load_kwargs["token"] = settings.hf_token
        if settings.hf_cache_dir:
            load_kwargs["cache_dir"] = str(settings.hf_cache_dir)

        logger.info(
            "Loading speech synthesis model source=%s device=%s local_only=%s",
            model_source,
            self.device,
            load_kwargs["local_files_only"],
        )
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_source, **load_kwargs)
            model = VitsModel.from_pretrained(model_source, **load_kwargs)
        except OSError as exc:
            raise SpeechSynthesisUnavailableError(
                "Speech synthesis model is not available locally. "
                "Download the configured Swahili TTS checkpoint from Hugging Face first."
            ) from exc
        except Exception as exc:
            raise SpeechSynthesisUnavailableError(
                f"Failed to initialize speech synthesis runtime: {exc}"
            ) from exc

        model = model.to(self.device)
        model.eval()
        sampling_rate = int(getattr(model.config, "sampling_rate", 16000))
        return _SpeechSynthesisRuntime(
            tokenizer=tokenizer,
            model=model,
            sampling_rate=sampling_rate,
        )

    async def _get_runtime(self) -> _SpeechSynthesisRuntime:
        if self._runtime is not None:
            return self._runtime
        async with self._runtime_lock:
            if self._runtime is None:
                loop = asyncio.get_running_loop()
                self._runtime = await loop.run_in_executor(None, self._build_runtime)
        return self._runtime

    def health_status(self, *, error: str | None = None) -> dict[str, Any]:
        configured_source = str(self.model_path) if self.model_path else self.model_name
        local_path_exists = self.model_path.exists() if self.model_path else None
        return {
            "ok": self._runtime is not None and error is None,
            "configured_source": configured_source,
            "device": self.device,
            "model_loaded": self._runtime is not None,
            "local_only": self._local_files_only(),
            "local_path_exists": local_path_exists,
            "error": error,
        }

    async def readiness_status(self) -> dict[str, Any]:
        error: str | None = None
        try:
            await self._get_runtime()
        except RuntimeError as exc:
            error = str(exc)
        return self.health_status(error=error)

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = MULTISPACE_PATTERN.sub(" ", text).strip()
        if not normalized:
            raise ValueError("Speech synthesis text is empty.")
        return normalized

    @staticmethod
    def _build_asset_id(
        *,
        patient_id: int | None,
        output_language: str,
        text: str,
        model_name: str | None = None,
    ) -> str:
        scope = f"patient-{patient_id}" if patient_id is not None else "shared"
        digest = hashlib.sha256(
            f"{model_name or ''}\u0000{output_language}\u0000{text}".encode()
        ).hexdigest()[:24]
        return f"speech/{output_language}/{scope}/{digest}.wav"

    @staticmethod
    def _serialize_waveform(waveform: np.ndarray, sampling_rate: int) -> bytes:
        clipped = np.clip(waveform, -1.0, 1.0)
        pcm16 = np.asarray(clipped * 32767.0, dtype=np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sampling_rate)
            handle.writeframes(pcm16.tobytes())
        return buffer.getvalue()

    def _run_synthesis(self, *, text: str) -> tuple[bytes, int]:
        runtime = self._runtime
        if runtime is None:
            raise SpeechSynthesisUnavailableError(
                "Speech synthesis runtime is not loaded."
            )
        tokenizer_inputs = runtime.tokenizer(text, return_tensors="pt")
        if hasattr(tokenizer_inputs, "to"):
            tokenizer_inputs = tokenizer_inputs.to(self.device)
        elif isinstance(tokenizer_inputs, dict):
            tokenizer_inputs = {
                key: value.to(self.device) if hasattr(value, "to") else value
                for key, value in tokenizer_inputs.items()
            }

        try:
            with torch.no_grad():
                waveform_tensor = runtime.model(**tokenizer_inputs).waveform
        except Exception as exc:
            raise SpeechSynthesisUnavailableError(
                f"Speech synthesis failed during inference: {exc}"
            ) from exc

        waveform = waveform_tensor.detach().cpu().float().numpy().squeeze()
        if waveform.size == 0:
            raise SpeechSynthesisUnavailableError(
                "Speech synthesis produced an empty waveform."
            )
        audio_bytes = self._serialize_waveform(waveform, runtime.sampling_rate)
        duration_ms = int(round((waveform.shape[-1] / runtime.sampling_rate) * 1000))
        return audio_bytes, duration_ms

    async def synthesize(
        self,
        *,
        text: str,
        output_language: str,
        response_mode: str,
        patient_id: int | None,
        conversation_id,
        message_id: int | None,
    ) -> SpeechSynthesisResult:
        normalized_text = self._normalize_text(text)
        asset_id = self._build_asset_id(
            patient_id=patient_id,
            output_language=output_language,
            text=normalized_text,
            model_name=self.model_name,
        )
        existing = await self.storage.get_asset_descriptor(asset_id=asset_id)
        if existing is not None:
            return SpeechSynthesisResult(
                audio_asset_id=existing.asset_id,
                output_language=output_language,
                response_mode=response_mode,
                audio_url=existing.audio_url,
                audio_duration_ms=existing.duration_ms,
                speech_locale="sw-KE",
                model_name=self.model_name,
            )

        await self._get_runtime()
        started = time.perf_counter()
        async with self._inference_lock:
            loop = asyncio.get_running_loop()
            audio_bytes, duration_ms = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    functools.partial(self._run_synthesis, text=normalized_text),
                ),
                timeout=settings.speech_synthesis_timeout_seconds,
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        descriptor = await self.storage.save_generated_audio(
            asset_id=asset_id,
            relative_path=asset_id,
            audio_bytes=audio_bytes,
            duration_ms=duration_ms,
            mime_type="audio/wav",
            metadata={
                "patient_id": patient_id,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": message_id,
                "output_language": output_language,
                "response_mode": response_mode,
                "speech_locale": "sw-KE",
                "model_name": self.model_name,
                "generated_text": normalized_text,
            },
        )
        logger.info(
            "speech.synthesize completed patient_id=%s message_id=%s duration_ms=%s latency_ms=%s",
            patient_id,
            message_id,
            duration_ms,
            latency_ms,
        )
        return SpeechSynthesisResult(
            audio_asset_id=descriptor.asset_id,
            output_language=output_language,
            response_mode=response_mode,
            audio_url=descriptor.audio_url,
            audio_duration_ms=descriptor.duration_ms,
            speech_locale="sw-KE",
            model_name=self.model_name,
        )
