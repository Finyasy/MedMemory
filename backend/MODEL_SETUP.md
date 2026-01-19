# Local Model Setup Guide

This guide explains how to use the locally downloaded and quantized MedGemma model.

## Quick Start

### 1. Download the Model

```bash
cd backend
python scripts/download_model.py
```

This will:
- Download `google/medgemma-1.5-4b-it` from Hugging Face
- Quantize it to INT4 (4-bit) for efficient inference
- Save it to `models/medgemma-1.5-4b-it/`

### 2. Configure Environment

Update `backend/.env`:

```env
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true
```

### 3. Restart Backend

The backend will automatically load the local model on startup:

```bash
docker compose -f docker-compose.dev.yml restart backend
```

Or if running locally:

```bash
uv run uvicorn app.main:app --reload
```

## Features

### INT4 Quantization

The model is quantized using 4-bit INT4 quantization with best practices:

- **Memory Efficient**: Reduces model size from ~8GB to ~4-6GB
- **NF4 Quantization**: Uses Normal Float 4-bit for optimal accuracy
- **Double Quantization**: Further reduces memory overhead
- **FP16 Compute**: Maintains accuracy by using float16 for computations

### Local Model Loading

When `LLM_MODEL_PATH` is set:
- Models are loaded from local directory (no Hugging Face download)
- Uses `local_files_only=True` for faster startup
- Works offline once downloaded

### Automatic Fallback

If local model is not available:
- Falls back to downloading from Hugging Face
- Uses the model ID specified in `LLM_MODEL`

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_MODEL` | Hugging Face model ID | `google/medgemma-1.5-4b-it` |
| `LLM_MODEL_PATH` | Local path to model directory | `None` (downloads from HF) |
| `LLM_QUANTIZE_4BIT` | Enable 4-bit quantization | `true` |
| `LLM_MAX_TOKENS` | Maximum tokens for generation | `2048` |
| `LLM_MAX_NEW_TOKENS` | Maximum new tokens to generate | `512` |
| `LLM_TEMPERATURE` | Generation temperature | `0.7` |

### Example Configurations

**Local Quantized Model (Recommended):**
```env
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true
```

**Local Full Precision:**
```env
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=false
```

**Download from Hugging Face:**
```env
# Don't set LLM_MODEL_PATH
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true
```

## Model Information

Check loaded model info:

```bash
curl http://localhost:8000/api/v1/chat/llm/info
```

Response includes:
- Model name and path
- Device (CUDA/CPU)
- Quantization status
- Memory usage
- Generation parameters

## Storage Requirements

### Download Size
- **Full Model**: ~8-10 GB
- **Quantized Model**: ~4-6 GB (after quantization)

### Memory Requirements
- **4-bit Quantized (CUDA)**: 6-8 GB GPU memory
- **Full Precision (CUDA)**: 8-10 GB GPU memory
- **CPU Inference**: 8-10 GB RAM (slower)

### Disk Space
- Allow 15-20 GB free for download and processing
- Final model size: ~4-6 GB (quantized) or ~8-10 GB (full)

## Troubleshooting

### Model Not Found
```
FileNotFoundError: Model path not found: models/medgemma-1.5-4b-it
```

**Solution**: Run the download script:
```bash
python scripts/download_model.py
```

### CUDA Required for Quantization
```
⚠️ Warning: 4-bit quantization requires CUDA. Loading full precision model.
```

**Solution**: 
- Use CUDA-enabled GPU, or
- Set `LLM_QUANTIZE_4BIT=false` in `.env`

### bitsandbytes Not Found
```
ImportError: bitsandbytes is required for 4-bit quantization
```

**Solution**: Install bitsandbytes:
```bash
pip install bitsandbytes
```

Note: bitsandbytes requires CUDA and may not work on macOS (except Apple Silicon).

### Out of Memory
If you get CUDA out of memory errors:
- Use 4-bit quantization (default)
- Reduce `LLM_MAX_NEW_TOKENS`
- Use a smaller model if available

## Advanced Usage

### Custom Model Path

Download to custom location:

```bash
python scripts/download_model.py --output-dir /path/to/custom/models/medgemma-1.5-4b-it
```

Then set in `.env`:
```env
LLM_MODEL_PATH=/path/to/custom/models/medgemma-1.5-4b-it
```

### Skip Quantization

Download full precision model:

```bash
python scripts/download_model.py --no-quantize
```

### Private Models

For private Hugging Face models:

```bash
python scripts/download_model.py --hf-token YOUR_HF_TOKEN
```

## Docker Setup

If using Docker, mount the models directory:

```yaml
volumes:
  - ./backend/models:/app/models:ro
```

This allows the container to access local models while keeping them read-only.
