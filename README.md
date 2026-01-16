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

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for better healthcare data management
</p>
