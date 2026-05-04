"""Schemas for speech input and output endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SpeechResponseMode = Literal["speech", "both"]


class SpeechTranscriptionResponse(BaseModel):
    """Response from English voice transcription."""

    transcript: str
    detected_language: str = "en"
    input_mode: Literal["voice"] = "voice"
    transcript_confidence: float | None = Field(None, ge=0.0, le=1.0)
    duration_ms: int | None = Field(None, ge=0)
    model_name: str | None = None


class SpeechSynthesisRequest(BaseModel):
    """Request to synthesize a grounded reply into audio."""

    text: str = Field(..., min_length=1, max_length=4000)
    patient_id: int | None = None
    conversation_id: UUID | None = None
    message_id: int | None = None
    output_language: str = Field("sw", max_length=10)
    response_mode: SpeechResponseMode = "speech"


class SpeechSynthesisResponse(BaseModel):
    """Response describing a synthesized speech asset."""

    audio_asset_id: str
    output_language: str = "sw"
    response_mode: SpeechResponseMode = "speech"
    audio_url: str | None = None
    audio_duration_ms: int | None = Field(None, ge=0)
    speech_locale: str | None = None
    model_name: str | None = None
