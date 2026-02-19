from fastapi import APIRouter, Response

from app.schemas.chat import LLMInfoResponse
from app.services.llm import LLMService
from app.services.llm.rag import RAGService

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


@router.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint."""
    counters = RAGService.get_global_guardrail_counters()
    lines = [
        "# HELP medmemory_guardrail_events_total Count of guardrail events.",
        "# TYPE medmemory_guardrail_events_total counter",
    ]
    if counters:
        for event in sorted(counters):
            value = counters[event]
            lines.append(f'medmemory_guardrail_events_total{{event="{event}"}} {value}')
    else:
        lines.append('medmemory_guardrail_events_total{event="none"} 0')
    body = "\n".join(lines) + "\n"
    return Response(body, media_type="text/plain; version=0.0.4")
