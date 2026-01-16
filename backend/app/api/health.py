from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {
        "status": "healthy",
        "service": "medmemory-api"
    }


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to MedMemory API",
        "docs": "/docs",
        "health": "/health"
    }
