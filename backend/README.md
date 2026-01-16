# MedMemory Backend

FastAPI backend for MedMemory - A Unified, Local-First Medical Memory for Human-Centered EHR Question Answering.

## Development

```bash
# Install dependencies with UV
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
