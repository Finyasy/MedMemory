# MedMemory Backend

FastAPI backend for MedMemory - A Unified, Local-First Medical Memory for Human-Centered EHR Question Answering.

## Development

```bash
# Install dependencies with UV
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Hybrid (Local Backend + Docker DB/Frontend)

Recommended for Apple Silicon so the LLM runs locally on MPS while keeping the DB/frontend containerized.

**Production-like frontend (Nginx):**
```bash
docker compose -f docker-compose.local-backend.yml up -d
```

**Vite dev frontend (hot reload):**
```bash
docker compose -f docker-compose.local-backend.dev.yml up -d
```

**Local backend prerequisites:**
- Ensure the MedGemma model is downloaded under `backend/models/medgemma-1.5-4b-it`.
- `backend/.env` should include `HF_TOKEN`, `LLM_MODEL_PATH=models/medgemma-1.5-4b-it`, and `LLM_QUANTIZE_4BIT=false`.
- The dev container sets `VITE_API_BASE=http://localhost:8000` so the browser talks directly to the local backend.
 - For offline mode (after models are downloaded), set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.

Then run the backend locally:
```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper:
```bash
../start-hybrid.sh dev
```

Stop or check status:
```bash
../stop-hybrid.sh dev
../status-hybrid.sh dev
```

**Verify model readiness:**
```bash
curl http://localhost:8000/api/v1/chat/llm/info \
  -H "Authorization: Bearer <YOUR_JWT>"
```

**Verify chat generation:**
```bash
curl -X POST http://localhost:8000/api/v1/chat/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -d '{"patient_id": 1, "question": "Summarize recent lab results."}'
```

**Get a JWT token:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Model Download (MedGemma)

The MedGemma model is gated on Hugging Face. You must accept the model terms and authenticate before downloading.

```bash
# From repo root
export HF_TOKEN=hf_your_token_here
python backend/scripts/download_model.py --model-id google/medgemma-1.5-4b-it
```

Notes:
- `HF_TOKEN` can also be set in `backend/.env`.
- For reproducible downloads in CI, pass `--revision <commit_hash>`.
- The script writes `model_metadata.json` and `download.log` into the model directory.
