# Hybrid Setup Fixes (Local Backend + Docker DB/Frontend)

## Issues Found and Fixed

### 1. ✅ Model Path Resolution Issue (FIXED)

**Problem:** 
- Model path was set as relative path (`models/medgemma-1.5-4b-it`) in config
- When `LLMService` initialized, it created a `Path` object but didn't resolve it relative to the backend directory
- This could cause issues when the working directory differs from the backend directory

**Fix Applied:**
- Updated `LLMService.__init__()` to resolve relative paths relative to the backend directory
- Added logic to detect if path is absolute, and if not, resolve it relative to `backend_dir`
- Backend directory is determined from `__file__` location: `Path(__file__).parent.parent.parent`

**File Changed:**
- `backend/app/services/llm/model.py` (lines 67-79)

### 2. ✅ Database Connection (VERIFIED)

**Status:** Working correctly
- Database URL: `postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory`
- Docker database is accessible on `localhost:5432` from local backend
- Connection tested and working

### 3. ⚠️ Missing Dependencies (NOTED)

**Issue:**
- `fitz` (PyMuPDF) module not found when importing services
- This is a dependency issue, not a configuration issue
- Should be installed via: `uv sync` or `pip install pymupdf`

**Note:** This doesn't affect model loading, but will cause import errors when the app starts.

### 4. ✅ Configuration Verification

**Current Settings (from .env):**
- `DATABASE_URL`: `postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory` ✅
- `LLM_MODEL_PATH`: `models/medgemma-1.5-4b-it` ✅ (now properly resolved)
- `LLM_QUANTIZE_4BIT`: `False` ✅ (correct for macOS/MPS)
- `DEBUG`: `True` ✅

## Testing the Fix

### Test Model Path Resolution:

```bash
cd backend
python -c "
from app.services.llm.model import LLMService
service = LLMService()
print(f'Model path: {service.model_path}')
print(f'Exists: {service.model_path.exists()}')
print(f'Device: {service.device}')
"
```

### Test Database Connection:

```bash
cd backend
python -c "
import asyncio
from app.database import init_db
asyncio.run(init_db())
print('Database connection successful!')
"
```

### Test Full Startup:

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Setup Instructions

### 1. Start Docker Services (DB + Frontend)

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory
docker compose up db frontend -d
```

### 2. Install Dependencies (if needed)

```bash
cd backend
uv sync
```

### 3. Start Backend Locally

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Verify Setup

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173 (or 5174)
- Database: localhost:5432

## Expected Behavior

1. **Model Loading:**
   - Model path should resolve to: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/medgemma-1.5-4b-it`
   - Device should auto-detect as `mps` on Apple Silicon
   - Model loads lazily on first use (not at startup)

2. **Database:**
   - Connects to Docker database on `localhost:5432`
   - Uses credentials from `.env` file

3. **Performance:**
   - MPS acceleration should work (2-5x faster than CPU)
   - No quantization (not supported on macOS)

## Troubleshooting

### Model Not Found Error

If you see "Model path not found":
1. Check model exists: `ls -la backend/models/medgemma-1.5-4b-it`
2. Verify path resolution: Check the fix in `model.py` lines 67-79
3. Ensure `.env` has: `LLM_MODEL_PATH=models/medgemma-1.5-4b-it`

### Database Connection Error

If database connection fails:
1. Check Docker is running: `docker compose ps`
2. Verify database is healthy: `docker compose ps db`
3. Test connection: `docker compose exec db pg_isready -U medmemory`
4. Check DATABASE_URL in `.env` matches Docker credentials

### Import Errors (fitz, etc.)

If you see module import errors:
```bash
cd backend
uv sync
# or
pip install pymupdf
```

## Summary

✅ **Fixed:** Model path resolution for relative paths  
✅ **Verified:** Database connection works correctly  
⚠️ **Noted:** Missing dependencies may need installation  
✅ **Ready:** Setup should work with local backend + Docker DB/Frontend
