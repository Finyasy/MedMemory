from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, context, documents, health, ingestion, memory, patients, records
from app.config import settings
from app.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    print("🧠 Starting MedMemory API...")
    try:
        await init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        print("⚠️  Server will not start without database connection")
        raise
    
    yield
    
    print("🔄 Shutting down MedMemory API...")
    try:
        await close_db()
        print("✅ Database connections closed")
    except Exception as e:
        print(f"⚠️  Error closing database: {e}")
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
app.include_router(ingestion.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(memory.router, prefix=settings.api_prefix)
app.include_router(context.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
