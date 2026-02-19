# MedMemory Backend

FastAPI backend for MedMemory - A Unified, Local-First Medical Memory for Human-Centered EHR Question Answering.

## Development

```bash
# Install dependencies with UV
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

```bash
# Run tests (preferred method)
uv run pytest

# If uv run fails (e.g., "system-configuration NULL object" panic in sandboxed environments)
# Use the helper script instead:
./run_tests.sh

# Or manually activate the venv:
source .venv/bin/activate && pytest
```

**Note:** If you encounter a `uv` panic with "system-configuration NULL object" (common in sandboxed macOS environments), use the `run_tests.sh` script or activate the virtual environment directly.

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
- Copy `backend/.env.example` to `backend/.env` and set secrets (`DATABASE_URL`, `JWT_SECRET_KEY`, `HF_TOKEN`).
- Keep grounding-safe defaults enabled in `backend/.env`:
  - `LLM_DO_SAMPLE=false`
  - `LLM_STRICT_GROUNDING=true`
  - `LLM_ALLOW_WEAK_FALLBACK=false`
  - `LLM_MIN_RELEVANCE_SCORE=0.45`
  - `LLM_REPETITION_PENALTY=1.1`
  - `LLM_REQUIRE_NUMERIC_CITATIONS=false` (set `true` for stricter patient-mode numeric citation enforcement)
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

**Apply live provider sync env config:**
```bash
cd backend
python scripts/apply_provider_sync_env.py \
  --env-file .env \
  --base-urls '<JSON_OR_PATH>' \
  --bearer-tokens '<JSON_OR_PATH>' \
  --api-keys '<JSON_OR_PATH>'
```

**Dry-run live provider sync (no ingestion writes):**
```bash
cd backend
python scripts/dry_run_provider_connections.py \
  --base-url http://localhost:8000/api/v1 \
  --patient-id 1 \
  --token "<JWT>"
```
If a provider endpoint is configured but unavailable/non-FHIR and
`PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN=true`, dry-run reports `local_fallback`
instead of failing.

## OCR Refinement + Vision Chat

### OCR refinement (Tesseract -> Gemma)
When processing PDFs/images, OCR output is cleaned and entities are extracted using the local MedGemma model.

**Requirements:**
- Tesseract installed and available on PATH
- OpenCV (installed via `uv sync`)

**Settings (in `backend/.env`):**
- `OCR_REFINEMENT_ENABLED=true`
- `OCR_REFINEMENT_MAX_NEW_TOKENS=384`
- `OCR_PREPROCESS_OPENCV=true`

**Fetch OCR refinement results:**
```bash
curl http://localhost:8000/api/v1/documents/<DOCUMENT_ID>/ocr \
  -H "Authorization: Bearer <YOUR_JWT>"
```

### Vision chat (MedGemma VLM)
Send an image and a prompt directly to the MedGemma vision model:
```bash
curl -X POST http://localhost:8000/api/v1/chat/vision \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -F "patient_id=1" \
  -F "prompt=Does this chest X-ray show signs of pneumonia?" \
  -F "image=@/path/to/xray.png"
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Hallucination Regression Eval

Run the fixed RAG guardrail regression set and generate gate-compatible metrics:

```bash
cd backend
uv run python scripts/evaluate_rag_hallucination.py \
  --eval-file data/hallucination_rag_eval/eval.jsonl \
  --output-dir artifacts/hallucination_eval/current
```

Then run the gate on the generated metrics:

```bash
cd backend
uv run python scripts/hallucination_regression_gate.py \
  --candidate-metrics artifacts/hallucination_eval/current/metrics_summary.json \
  --candidate-scope baseline \
  --baseline-metrics data/hallucination_eval/baseline_metrics_summary.json \
  --baseline-scope baseline \
  --output-json artifacts/hallucination_eval/gate_report.json
```

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
