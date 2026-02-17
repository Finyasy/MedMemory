# 🧠 MedMemory

**A Unified, Local-First Medical Memory for Human-Centered Electronic Health Records (EHR) Question Answering**

![MedMemory](https://img.shields.io/badge/MedMemory-v0.1.0-10b981?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)
![UV](https://img.shields.io/badge/UV-Package_Manager-7C3AED?style=flat-square)

---

## ✨ Features

- 🔒 **Local-First Privacy** - Your medical data stays on your device
- 💬 **Intelligent Q&A** - Ask questions about your health records in natural language
- 📋 **Unified Records** - Consolidate records from multiple providers
- ⚡ **Fast & Modern** - Built with FastAPI, React, and UV for speed

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI, Pydantic, Uvicorn |
| **Frontend** | React 18, TypeScript, Vite |
| **Package Management** | UV (Python), npm (Node.js) |
| **Containerization** | Docker, Docker Compose |

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Or for local development:
  - [UV](https://docs.astral.sh/uv/) (Python package manager)
  - [Node.js](https://nodejs.org/) 20+

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd MedMemory

# Build and run with Docker Compose
docker compose up --build

# Access the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 1B: Hybrid (Local Backend + Docker DB/Frontend)

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
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper:
```bash
./start-hybrid.sh dev
```

By default, the helper starts the backend in stable no-reload mode and waits for Docker DB health before launching API startup. To opt into auto-reload locally:
```bash
HYBRID_BACKEND_RELOAD=1 ./start-hybrid.sh dev
```

Stop or check status:
```bash
./stop-hybrid.sh dev
./status-hybrid.sh dev
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

### OCR Refinement + Vision Chat

OCR output is cleaned and structured by the local MedGemma model after document processing.

**Fetch OCR refinement results:**
```bash
curl http://localhost:8000/api/v1/documents/<DOCUMENT_ID>/ocr \
  -H "Authorization: Bearer <YOUR_JWT>"
```

**Vision chat (MedGemma VLM):**
```bash
curl -X POST http://localhost:8000/api/v1/chat/vision \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -F "patient_id=1" \
  -F "prompt=Does this chest X-ray show signs of pneumonia?" \
  -F "image=@/path/to/xray.png"
```

### Option 2: Local Development

**Backend:**
```bash
cd backend

# Install dependencies with UV
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Access the app at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs

---

## 🐳 Docker Commands

```bash
# Production build
docker compose up --build -d

# Development with hot reload
docker compose -f docker-compose.dev.yml up

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild specific service
docker compose build backend
docker compose build frontend
```

---

## 📁 Project Structure

```
MedMemory/
├── backend/
│   ├── app/
│   │   ├── api/           # API route handlers
│   │   ├── models/        # Database models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── config.py      # Settings
│   │   └── main.py        # FastAPI app
│   ├── pyproject.toml     # UV dependencies
│   ├── Dockerfile
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── api.ts         # API client
│   │   ├── types.ts       # TypeScript types
│   │   ├── App.tsx        # Main component
│   │   └── *.css          # Styles
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml      # Production
├── docker-compose.dev.yml  # Development
└── README.md
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/records` | List all records |
| POST | `/api/v1/records` | Create a record |
| GET | `/api/v1/records/{id}` | Get a specific record |

---

## 🛠️ Development

### Adding Python Dependencies

```bash
cd backend
uv add <package-name>
```

### Adding Frontend Dependencies

```bash
cd frontend
npm install <package-name>
```

### Running Tests

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
npm run test
```

### Hallucination Rollout Automation

Run the full local hallucination eval + gate pipeline:

```bash
./scripts/automate_hallucination_next_steps.sh --local-only
```

Run end-to-end automation (local checks + push + PR + nightly dispatch + artifact verification):

```bash
# Optional: set webhook secret value before running
export HALLUCINATION_ALERT_WEBHOOK="https://hooks.slack.com/services/..."
./scripts/automate_hallucination_next_steps.sh --base=main
```

Requirements for GitHub automation mode:
- `gh` CLI installed
- `gh auth login` completed
- current branch is a feature branch (not `main`)

If `gh` is unavailable or not authenticated, the script still completes local
hallucination evaluation/gate checks and exits without failing.

---

## 🤖 Model Download (MedGemma)

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

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for better healthcare data management
</p>
