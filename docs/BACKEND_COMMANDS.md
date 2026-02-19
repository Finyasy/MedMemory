# Backend Commands Reference

## Quick Start

### Manual Start (Foreground)
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Manual Start (Background)
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
```

### Using Startup Script
```bash
cd backend
./start-backend.sh
```

## Auto-Restart Options

### Option 1: Built-in `--reload` (Already Enabled)
The `--reload` flag automatically restarts the backend when code changes are detected.

**Pros:**
- ✅ Already enabled in the command above
- ✅ No additional setup needed
- ✅ Works out of the box

**Cons:**
- ⚠️ Can be slower on large codebases
- ⚠️ May miss some file changes

### Option 2: Faster Reload with `watchfiles`
For faster auto-reload, install `watchfiles`:

```bash
cd backend
uv add watchfiles --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Uvicorn will automatically use `watchfiles` if available.

### Option 3: Using `nodemon` (Alternative)
If you prefer a Node.js-style watcher:

```bash
# Install nodemon globally
npm install -g nodemon

# Create nodemon.json in backend/
{
  "watch": ["app"],
  "ext": "py",
  "ignore": ["tests", "*.pyc"],
  "exec": "uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
}

# Run with nodemon
nodemon
```

### Option 4: Systemd Service (Production)
For production auto-restart on system reboot:

```bash
# Create /etc/systemd/system/medmemory-backend.service
[Unit]
Description=MedMemory Backend API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/Users/bryan.bosire/anaconda_projects/MedMemory/backend
ExecStart=/opt/anaconda3/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable medmemory-backend
sudo systemctl start medmemory-backend
```

## Stop Backend

### Kill by Port
```bash
lsof -ti:8000 | xargs kill -9
```

### Kill by Process Name
```bash
pkill -f "uvicorn app.main:app"
```

## Check Backend Status

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Check if Running
```bash
lsof -ti:8000 && echo "Backend is running" || echo "Backend is not running"
```

## Database Migrations

If you use the **Clinician portal** (signup at `/clinician`), ensure the doctor-dashboard migration is applied:

```bash
cd backend
uv run alembic upgrade head
```

Note: The subcommand is **`upgrade`**; `head` is the revision (e.g. `alembic upgrade head`, not `alembic head`).

If clinician signup returns "Database schema may be out of date", run the command above and retry.

## Troubleshooting

### Port Already in Use
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Dependencies Not Installed
```bash
cd backend
uv sync
```

### Backend Crashes on Startup
Check logs:
```bash
tail -f backend-dev.log
# or if running in foreground, check terminal output
```

## Recommended Setup

For development, use:
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

This gives you:
- ✅ Auto-reload on code changes
- ✅ Easy to stop (Ctrl+C)
- ✅ See logs in real-time
- ✅ No additional tools needed
