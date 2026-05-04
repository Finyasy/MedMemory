"""Boundary for Swahili speech synthesis runtime selection."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.schemas.speech import SpeechSynthesisRequest, SpeechSynthesisResponse
from app.services.speech.synthesize import (
    SpeechSynthesisResult,
    SpeechSynthesisService,
    SpeechSynthesisUnavailableError,
)

logger = logging.getLogger("medmemory")

_SUPPORTED_BACKENDS = {"in_process", "http"}
_INTERNAL_SYNTHESIZE_PATH = "/internal/v1/speech/synthesize"
_INTERNAL_HEALTH_PATH = "/internal/v1/health"


class SpeechSynthesisBoundary:
    """Select between in-process and dedicated-service speech synthesis backends."""

    _instance: SpeechSynthesisBoundary | None = None

    def __init__(
        self,
        *,
        backend_mode: str | None = None,
        service_base_url: str | None = None,
        service_timeout_seconds: int | None = None,
        service_api_key: str | None = None,
        local_service: SpeechSynthesisService | None = None,
    ) -> None:
        resolved_mode = (backend_mode or settings.speech_synthesis_backend).strip().lower()
        if resolved_mode not in _SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported speech synthesis backend '{resolved_mode}'. Expected one of: "
                f"{', '.join(sorted(_SUPPORTED_BACKENDS))}."
            )
        self.backend_mode = resolved_mode
        self.service_base_url = (
            service_base_url or settings.speech_synthesis_service_base_url or ""
        ).rstrip("/")
        self.service_timeout_seconds = (
            service_timeout_seconds or settings.speech_synthesis_service_timeout_seconds
        )
        self.service_api_key = service_api_key or settings.speech_service_internal_api_key
        self._local_service = local_service

    @classmethod
    def get_instance(cls) -> SpeechSynthesisBoundary:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _request_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.service_api_key:
            headers["X-Speech-Service-Key"] = self.service_api_key
        return headers

    def _get_local_service(self) -> SpeechSynthesisService:
        if self._local_service is None:
            self._local_service = SpeechSynthesisService.get_instance()
        return self._local_service

    def _service_url(self, path: str) -> str:
        if not self.service_base_url:
            raise SpeechSynthesisUnavailableError(
                "Speech synthesis service base URL is not configured for HTTP boundary mode."
            )
        return f"{self.service_base_url}{path}"

    @staticmethod
    def _result_from_response(payload: SpeechSynthesisResponse) -> SpeechSynthesisResult:
        return SpeechSynthesisResult(
            audio_asset_id=payload.audio_asset_id,
            output_language=payload.output_language,
            response_mode=payload.response_mode,
            audio_url=payload.audio_url,
            audio_duration_ms=payload.audio_duration_ms,
            speech_locale=payload.speech_locale,
            model_name=payload.model_name,
        )

    async def _synthesize_via_http(
        self,
        *,
        text: str,
        output_language: str,
        response_mode: str,
        patient_id: int | None,
        conversation_id,
        message_id: int | None,
    ) -> SpeechSynthesisResult:
        payload = SpeechSynthesisRequest(
            text=text,
            patient_id=patient_id,
            conversation_id=conversation_id,
            message_id=message_id,
            output_language=output_language,
            response_mode=response_mode,  # type: ignore[arg-type]
        )
        try:
            async with httpx.AsyncClient(
                timeout=self.service_timeout_seconds,
            ) as client:
                response = await client.post(
                    self._service_url(_INTERNAL_SYNTHESIZE_PATH),
                    json=payload.model_dump(mode="json"),
                    headers=self._request_headers(),
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise SpeechSynthesisUnavailableError(
                "Dedicated speech synthesis service returned an error: "
                f"{exc.response.status_code} {detail or exc.response.reason_phrase}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeechSynthesisUnavailableError(
                f"Dedicated speech synthesis service is unavailable: {exc}"
            ) from exc

        return self._result_from_response(
            SpeechSynthesisResponse.model_validate(response.json())
        )

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
        if self.backend_mode == "http":
            return await self._synthesize_via_http(
                text=text,
                output_language=output_language,
                response_mode=response_mode,
                patient_id=patient_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        return await self._get_local_service().synthesize(
            text=text,
            output_language=output_language,
            response_mode=response_mode,
            patient_id=patient_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    async def readiness_status(self) -> dict[str, Any]:
        if self.backend_mode == "in_process":
            status = await self._get_local_service().readiness_status()
            return {
                **status,
                "boundary_backend": self.backend_mode,
            }
        try:
            async with httpx.AsyncClient(
                timeout=self.service_timeout_seconds,
            ) as client:
                response = await client.get(
                    self._service_url(_INTERNAL_HEALTH_PATH),
                    headers=self._request_headers(),
                )
                response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise SpeechSynthesisUnavailableError(
                    "Dedicated speech synthesis health response was not an object."
                )
            return {
                **payload,
                "boundary_backend": self.backend_mode,
                "service_base_url": self.service_base_url,
            }
        except Exception as exc:
            logger.warning("speech.synthesis boundary health check failed: %s", exc)
            return {
                "ok": False,
                "model_loaded": False,
                "configured_source": self.service_base_url or None,
                "boundary_backend": self.backend_mode,
                "service_base_url": self.service_base_url or None,
                "error": str(exc),
            }
