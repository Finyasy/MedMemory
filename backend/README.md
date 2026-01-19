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
