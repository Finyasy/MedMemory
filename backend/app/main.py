from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, context, documents, health, ingestion, memory, patients, records
from app.api.deps import get_authenticated_user
from app.config import settings
from app.database import close_db, init_db
from app.services.embeddings import EmbeddingService
from app.logging import configure_logging, request_id_var

configure_logging()
logger = logging.getLogger("medmemory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    logger.info("Starting MedMemory API")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Failed to initialize database")
        raise

    try:
        # Preload embedding model to avoid first-request stall.
        EmbeddingService.get_instance().model
        logger.info("Embedding model loaded")
    except Exception:
        logger.exception("Failed to preload embedding model")
    
    yield
    
    logger.info("Shutting down MedMemory API")
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
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
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
