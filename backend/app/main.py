import logging
import os
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    apple_health,
    auth,
    chat,
    clinician,
    context,
    dashboard,
    dependents,
    documents,
    health,
    ingestion,
    insights,
    memory,
    patient_access,
    patients,
    profile,
    records,
    speech,
)
from app.api.deps import get_authenticated_user
from app.config import settings
from app.database import close_db, init_db
from app.logging import configure_logging, request_id_var
from app.services.observability import ObservabilityRegistry
from app.services.dashboard_sync_scheduler import get_dashboard_sync_scheduler
from app.services.embeddings import EmbeddingService, MissingMLDependencyError

configure_logging()
logger = logging.getLogger("medmemory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    dashboard_sync_scheduler = get_dashboard_sync_scheduler()
    logger.info("Starting MedMemory API")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Failed to initialize database")
        raise

    try:
        EmbeddingService.get_instance().model
        logger.info("Embedding model loaded")
    except MissingMLDependencyError as exc:
        logger.error("Embedding startup dependency check failed: %s", exc)
        if settings.startup_require_embeddings:
            raise RuntimeError(str(exc)) from exc
        logger.warning("Continuing without embedding preload because STARTUP_REQUIRE_EMBEDDINGS=false")
    except Exception:
        logger.exception("Failed to preload embedding model")
        if settings.startup_require_embeddings:
            raise
        logger.warning("Continuing without embedding preload because STARTUP_REQUIRE_EMBEDDINGS=false")

    preload_llm = os.getenv("PRELOAD_LLM_ON_STARTUP", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if preload_llm:
        try:
            from app.services.llm.model import LLMService

            llm_service = LLMService.get_instance()
            _ = llm_service.model
            _ = llm_service.processor
            logger.info("LLM model and processor loaded, warming up...")
            logger.info("LLM model ready")
        except Exception:
            logger.exception("Failed to preload LLM model (will load on first request)")
    else:
        logger.info(
            "Skipping LLM preload at startup. Set PRELOAD_LLM_ON_STARTUP=1 to enable."
        )

    try:
        await dashboard_sync_scheduler.start()
    except Exception:
        logger.exception("Failed to start dashboard sync scheduler")

    yield

    logger.info("Shutting down MedMemory API")
    try:
        await dashboard_sync_scheduler.stop()
    except Exception:
        logger.exception("Failed to stop dashboard sync scheduler cleanly")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception:
        logger.exception("Error closing database")
    logger.info("MedMemory API shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    # MedMemory API
    
    A Unified, Local-First Medical Memory for Human-Centered EHR Question Answering.
    
    ## Features
    
    - **Patient Management** - Store and manage patient records
    - **Medical Records** - Labs, medications, encounters, documents
    - **Semantic Memory** - Vector embeddings for intelligent retrieval
    - **AI Reasoning** - Natural language Q&A over medical history
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers.setdefault("X-Request-Id", request_id)
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        ObservabilityRegistry.get_instance().record_http_request(
            method=request.method,
            path=route_path,
            status_code=status_code,
            duration_ms=(perf_counter() - started) * 1000.0,
        )
        request_id_var.reset(token)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(self), camera=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    )
    if not settings.debug:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(
    patients.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    records.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    ingestion.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    documents.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    memory.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    context.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    chat.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    speech.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    insights.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    dashboard.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    apple_health.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    profile.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(
    dependents.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)
app.include_router(clinician.router, prefix=settings.api_prefix)
app.include_router(
    patient_access.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(get_authenticated_user)],
)


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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Validation error",
                "status_code": 422,
                "type": "validation_error",
                "details": exc.errors(),
                "request_id": request_id_var.get(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "status_code": 500,
                "type": "server_error",
                "request_id": request_id_var.get(),
            }
        },
    )
