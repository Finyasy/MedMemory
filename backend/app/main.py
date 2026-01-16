from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, records, patients
from app.config import settings
from app.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    print("🧠 Starting MedMemory API...")
    await init_db()
    print("✅ Database initialized")
    
    yield
    
    print("🔄 Shutting down MedMemory API...")
    await close_db()
    print("👋 Goodbye!")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(patients.router, prefix=settings.api_prefix)
app.include_router(records.router, prefix=settings.api_prefix)
