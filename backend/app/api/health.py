from fastapi import APIRouter, Response

from app.schemas.chat import LLMInfoResponse
from app.services.observability import ObservabilityRegistry
from app.services.llm import LLMService
from app.services.llm.rag import RAGService
from app.services.speech.synthesis_boundary import SpeechSynthesisBoundary
from app.services.speech.transcribe import SpeechTranscriptionService

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy", "service": "medmemory-api"}


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {"message": "Welcome to MedMemory API", "docs": "/docs", "health": "/health"}


@router.get("/llm/info", response_model=LLMInfoResponse)
async def get_llm_info():
    """Get information about the loaded LLM model.

    This endpoint is public and does not require authentication
    as it only returns informational metadata about the LLM configuration.
    """
    llm_service = LLMService.get_instance()
    info = llm_service.get_model_info()

    return LLMInfoResponse(**info)


@router.get("/health/llm")
async def llm_health():
    """Lightweight LLM health endpoint for frontend checks."""
    llm_service = LLMService.get_instance()
    info = llm_service.get_model_info()
    return {"ok": True, "llm": info}


@router.get("/health/speech")
async def speech_health():
    """Lightweight speech readiness endpoint for frontend checks."""
    return {
        "ok": True,
        "transcription": await SpeechTranscriptionService.get_instance().readiness_status(),
        "synthesis": await SpeechSynthesisBoundary.get_instance().readiness_status(),
    }


@router.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint."""
    counters = RAGService.get_global_guardrail_counters()
    body = ObservabilityRegistry.get_instance().render_prometheus(
        guardrail_counters=counters,
    )
    return Response(body, media_type="text/plain; version=0.0.4")
