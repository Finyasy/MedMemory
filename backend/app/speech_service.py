"""Dedicated internal app for Swahili TTS generation."""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging import configure_logging, request_id_var
from app.schemas.speech import SpeechSynthesisRequest, SpeechSynthesisResponse
from app.services.speech.synthesize import SpeechSynthesisService
from app.services.speech.validators import (
    validate_response_mode,
    validate_synthesis_language,
)

configure_logging()
logger = logging.getLogger("medmemory")


def _require_internal_key(
    x_speech_service_key: str | None = Header(default=None, alias="X-Speech-Service-Key"),
) -> None:
    expected = settings.speech_service_internal_api_key
    if not expected:
        return
    if x_speech_service_key != expected:
        raise HTTPException(status_code=401, detail="Invalid speech service credentials.")


app = FastAPI(
    title="MedMemory Speech Service",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers.setdefault("X-Request-Id", request_id)
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
                "type": "http_error",
                "request_id": request_id_var.get(),
            }
        },
    )


@app.get("/internal/v1/health", dependencies=[Depends(_require_internal_key)])
async def internal_health():
    """Readiness check for the dedicated TTS worker."""
    readiness = await SpeechSynthesisService.get_instance().readiness_status()
    return {
        **readiness,
        "service": "medmemory-speech",
    }


@app.post(
    "/internal/v1/speech/synthesize",
    response_model=SpeechSynthesisResponse,
    dependencies=[Depends(_require_internal_key)],
)
async def synthesize_speech(request: SpeechSynthesisRequest):
    """Generate a persisted Swahili speech asset from finalized text."""
    try:
        normalized_language = validate_synthesis_language(request.output_language)
        normalized_response_mode = validate_response_mode(
            request.response_mode,
            allow_text=False,
        )
        result = await SpeechSynthesisService.get_instance().synthesize(
            text=request.text,
            output_language=normalized_language,
            response_mode=normalized_response_mode,
            patient_id=request.patient_id,
            conversation_id=request.conversation_id,
            message_id=request.message_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.info(
        "speech.service synthesize completed patient_id=%s message_id=%s model=%s",
        request.patient_id,
        request.message_id,
        result.model_name,
    )
    return SpeechSynthesisResponse(
        audio_asset_id=result.audio_asset_id,
        output_language=result.output_language,
        response_mode=result.response_mode,  # type: ignore[arg-type]
        audio_url=result.audio_url,
        audio_duration_ms=result.audio_duration_ms,
        speech_locale=result.speech_locale,
        model_name=result.model_name,
    )
