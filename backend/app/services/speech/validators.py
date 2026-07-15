"""Validation helpers for speech endpoints."""

from __future__ import annotations

from fastapi import UploadFile

from app.config import settings

SUPPORTED_TRANSCRIPTION_LANGUAGES = frozenset({"en"})
SUPPORTED_SYNTHESIS_LANGUAGES = frozenset({"sw"})
SUPPORTED_CHAT_INPUT_MODES = frozenset({"text", "voice"})
SUPPORTED_CHAT_RESPONSE_MODES = frozenset({"text", "speech", "both"})


def normalize_language(value: str | None, *, fallback: str) -> str:
    if not value or not isinstance(value, str):
        return fallback
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "english": "en",
        "eng": "en",
        "en-us": "en",
        "en-gb": "en",
        "sw": "sw",
        "swa": "sw",
        "swahili": "sw",
        "kiswahili": "sw",
        "sw-ke": "sw",
    }
    return aliases.get(normalized, normalized)


def validate_transcription_language(language: str | None) -> str:
    normalized = normalize_language(language, fallback="en")
    if normalized not in SUPPORTED_TRANSCRIPTION_LANGUAGES:
        raise ValueError("Only English voice transcription is supported.")
    return normalized


def validate_synthesis_language(language: str | None) -> str:
    normalized = normalize_language(language, fallback="sw")
    if normalized not in SUPPORTED_SYNTHESIS_LANGUAGES:
        raise ValueError("Only Swahili speech synthesis is supported.")
    return normalized


def validate_response_mode(value: str | None, *, allow_text: bool = True) -> str:
    raw_value = value if isinstance(value, str) else ("text" if allow_text else "speech")
    normalized = raw_value.strip().lower()
    allowed = SUPPORTED_CHAT_RESPONSE_MODES if allow_text else {"speech", "both"}
    if normalized not in allowed:
        raise ValueError(
            "Unsupported response mode. Expected one of: "
            + ", ".join(sorted(allowed))
        )
    return normalized


def validate_input_mode(value: str | None) -> str:
    raw_value = value if isinstance(value, str) else "text"
    normalized = raw_value.strip().lower()
    if normalized not in SUPPORTED_CHAT_INPUT_MODES:
        raise ValueError("Unsupported input mode. Expected 'text' or 'voice'.")
    return normalized


def validate_audio_upload(audio: UploadFile) -> None:
    if not getattr(audio, "filename", None):
        raise ValueError("Audio upload is required.")
    content_type = getattr(audio, "content_type", None) or ""
    if content_type and (
        content_type.startswith("audio/")
        or content_type in {"application/octet-stream", "application/ogg"}
    ):
        return
    raise ValueError("Only audio uploads are supported.")


def validate_audio_payload_size(audio_bytes: bytes) -> None:
    if not audio_bytes:
        raise ValueError("Audio upload is empty.")
    if len(audio_bytes) > settings.speech_transcription_max_upload_bytes:
        raise ValueError(
            "Audio upload exceeds the configured size limit for transcription."
        )


def validate_audio_duration(duration_ms: int | None) -> None:
    if duration_ms is None:
        return
    max_duration_ms = settings.speech_transcription_max_duration_seconds * 1000
    if duration_ms > max_duration_ms:
        raise ValueError(
            "Audio clip is longer than the configured transcription limit."
        )


def validate_transcript_text(transcript: str) -> str:
    normalized = transcript.strip()
    if not normalized:
        raise ValueError("Transcription produced an empty transcript.")
    return normalized


def validate_transcript_confidence(confidence: float | None) -> None:
    if confidence is None:
        return
    if confidence < settings.speech_transcription_min_confidence:
        raise ValueError(
            "Speech transcription confidence is too low. Please retry in a quieter "
            "environment or type the question manually."
        )
