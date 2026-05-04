"""Speech API endpoints for transcription and synthesis."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_authorized_patient
from app.database import get_db
from app.models import User
from app.schemas.speech import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SpeechTranscriptionResponse,
)
from app.services.speech import (
    SpeechStorageService,
    SpeechSynthesisBoundary,
    SpeechTranscriptionService,
)
from app.services.speech.validators import (
    validate_audio_upload,
    validate_response_mode,
    validate_synthesis_language,
    validate_transcription_language,
)

router = APIRouter(prefix="/speech", tags=["Speech"])
logger = logging.getLogger("medmemory")


@router.post("/transcribe", response_model=SpeechTranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    patient_id: int | None = Form(None),
    clinician_mode: bool = Form(False),
    language: str = Form("en"),
):
    """Transcribe an English audio clip into text."""
    try:
        normalized_language = validate_transcription_language(language)
        validate_audio_upload(audio)
        result = await SpeechTranscriptionService.get_instance().transcribe(
            audio=audio,
            language=normalized_language,
            patient_id=patient_id,
            clinician_mode=clinician_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.info(
        "speech.transcribe request accepted patient_id=%s clinician_mode=%s model=%s",
        patient_id,
        clinician_mode,
        result.model_name,
    )
    return SpeechTranscriptionResponse(
        transcript=result.transcript,
        detected_language=result.detected_language,
        transcript_confidence=result.transcript_confidence,
        duration_ms=result.duration_ms,
        model_name=result.model_name,
    )


@router.post("/synthesize", response_model=SpeechSynthesisResponse)
async def synthesize_speech(request: SpeechSynthesisRequest):
    """Create a Swahili speech asset from a finalized grounded reply."""
    try:
        normalized_language = validate_synthesis_language(request.output_language)
        normalized_response_mode = validate_response_mode(
            request.response_mode,
            allow_text=False,
        )
        result = await SpeechSynthesisBoundary.get_instance().synthesize(
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

    return SpeechSynthesisResponse(
        audio_asset_id=result.audio_asset_id,
        output_language=result.output_language,
        response_mode=result.response_mode,  # type: ignore[arg-type]
        audio_url=result.audio_url,
        audio_duration_ms=result.audio_duration_ms,
        speech_locale=result.speech_locale,
        model_name=result.model_name,
    )


@router.get("/health")
async def speech_health():
    """Lightweight health endpoint for speech services."""
    return {
        "transcription": await SpeechTranscriptionService.get_instance().readiness_status(),
        "synthesis": await SpeechSynthesisBoundary.get_instance().readiness_status(),
    }


@router.get("/assets/{asset_id:path}")
async def get_speech_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Download a generated speech asset after checking patient access."""
    try:
        descriptor = await SpeechStorageService.get_instance().read_generated_audio(
            asset_id=asset_id
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Speech asset not found.") from exc

    patient_id = descriptor.metadata.get("patient_id")
    if isinstance(patient_id, int):
        await get_authorized_patient(
            patient_id=patient_id,
            db=db,
            current_user=current_user,
            scope="chat",
        )

    return FileResponse(
        descriptor.absolute_path,
        media_type=descriptor.mime_type,
        filename=descriptor.absolute_path.name,
    )
