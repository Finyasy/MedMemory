from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, records
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A Unified, Local-First Medical Memory for Human-Centered EHR Question Answering",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(records.router, prefix=settings.api_prefix)
