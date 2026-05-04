"""Speech service boundaries for transcription, synthesis, and asset storage."""

from app.services.speech.storage import SpeechAssetDescriptor, SpeechStorageService
from app.services.speech.synthesis_boundary import SpeechSynthesisBoundary
from app.services.speech.synthesize import SpeechSynthesisResult, SpeechSynthesisService
from app.services.speech.transcribe import (
    SpeechTranscriptionResult,
    SpeechTranscriptionService,
)

__all__ = [
    "SpeechAssetDescriptor",
    "SpeechStorageService",
    "SpeechSynthesisBoundary",
    "SpeechSynthesisResult",
    "SpeechSynthesisService",
    "SpeechTranscriptionResult",
    "SpeechTranscriptionService",
]
