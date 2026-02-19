# Model Download Scripts

Scripts for downloading and managing LLM models for local use.

## Apply Provider Sync Env

Write live provider sync settings into `backend/.env` from JSON maps (inline JSON
or file paths):

```bash
cd backend
python scripts/apply_provider_sync_env.py \
  --env-file .env \
  --base-urls '{"digital_health_agency_dha":"https://med.kenya-hie.health/fhir"}' \
  --bearer-tokens '{"digital_health_agency_dha":"<token>"}' \
  --api-keys '{}'
```

Tip:
- Keep credentials in files ignored by git, then pass file paths to `--base-urls`,
  `--bearer-tokens`, and `--api-keys`.
- Use `--print-only` to preview changes without writing.

## Provider Sync Dry-Run

Validate live provider connectivity for one patient's dashboard connections without
writing ingested records:

```bash
cd backend
python scripts/dry_run_provider_connections.py \
  --base-url http://localhost:8000/api/v1 \
  --patient-id 1 \
  --token "<JWT>"
```

Useful options:
- `--provider-slug kenya_health_information_system_khis` to validate one provider.
- `--include-inactive` to include disabled connections.
- `--json` for machine-readable output.
- `--insecure` for local/self-signed TLS endpoints.

Fallback behavior:
- If live connectivity fails and `PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN=true`,
  dry-run reports `mode=local_fallback` and returns success (`ok=true`).

Exit codes:
- `0` all selected dry-runs passed.
- `1` at least one connection failed.
- `2` request/auth/setup failure.

## One-Time Eval Fixture Cleanup

Remove stale tone-eval fixture data (`[EVAL:` / `EVAL_FIXTURE`) from:
- `memory_chunks` (`chunk_type=eval_fixture` and marker content)
- `records` (eval-prefixed titles/marker content)
- `conversation_messages` (marker content)

Dry-run first:

```bash
cd backend
uv run python scripts/cleanup_eval_fixtures.py
```

Apply deletion:

```bash
cd backend
uv run python scripts/cleanup_eval_fixtures.py --apply
```

## Download Model Script

### Usage

Download and quantize MedGemma model for local use:

```bash
python scripts/download_model.py --model-id google/medgemma-1.5-4b-it --output-dir models/medgemma-1.5-4b-it
```

### Options

- `--model-id`: Hugging Face model identifier (default: `google/medgemma-1.5-4b-it`)
- `--output-dir`: Local directory to save the model (default: `models/medgemma-1.5-4b-it`)
- `--no-quantize`: Skip 4-bit quantization (use full precision model)
- `--hf-token`: Hugging Face token for private models (optional)

### Quantization

By default, the script uses **INT4 (4-bit) quantization** with best practices:

- **NF4 quantization type**: Normal Float 4-bit for optimal accuracy
- **Double quantization**: Reduces memory usage further
- **FP16 compute dtype**: Uses float16 for computations while storing weights in 4-bit
- **Automatic device mapping**: Optimizes model placement across GPUs

**Requirements for quantization:**
- CUDA-enabled GPU (NVIDIA)
- `bitsandbytes` package installed
- Sufficient GPU memory (~4-6 GB for 4B model)

### Model Storage

Models are saved to the `models/` directory by default:
```
backend/
├── models/
│   └── medgemma-1.5-4b-it/
│       ├── config.json
│       ├── pytorch_model.bin (or safetensors)
│       ├── tokenizer.json
│       └── ...
```

### Configuration

After downloading, update your `.env` file:

```env
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true
```

The application will automatically use the local model when `LLM_MODEL_PATH` is set.

### Download Progress

The download process includes:
1. **Download model files** from Hugging Face (~8-10 GB)
2. **Quantize to INT4** if CUDA is available (~4-6 GB final size)
3. **Verify tokenizer** works correctly
4. **Test model loading** to ensure everything works

Check download progress:
```bash
tail -f model_download.log
```

### Troubleshooting

**CUDA not available:**
- Quantization requires CUDA. The script will fall back to full precision if CUDA is not available.
- Full precision models require ~8-10 GB of RAM/VRAM.

**bitsandbytes not installed:**
- Install with: `pip install bitsandbytes`
- Note: bitsandbytes requires CUDA

**Out of memory:**
- Try using 8-bit quantization instead: `--no-quantize` and manually set 8-bit in config
- Or use CPU inference (no quantization)

**Model path not found:**
- Make sure the download completed successfully
- Check that `LLM_MODEL_PATH` in `.env` matches the actual path

### Best Practices

1. **Disk Space**: Ensure you have at least 15-20 GB free for downloading and processing
2. **GPU Memory**: For 4-bit quantization, 6-8 GB GPU memory is recommended
3. **Internet**: Model download requires stable internet connection (~8-10 GB download)
4. **Time**: Download and quantization can take 10-30 minutes depending on hardware

---

## Real Use-Case QLoRA Pipeline

These scripts implement a practical decision loop for MedMemory:

1. Build a small eval set from real conversations (50-200 examples).
2. Fine-tune with QLoRA on the train split.
3. Compare baseline vs tuned outputs using factuality and accuracy proxies.

### Install Fine-Tuning Dependencies

```bash
cd backend
uv sync --group finetune
```

### 1) Build Dataset from Real Use Cases

```bash
cd backend
uv run python scripts/build_real_usecase_dataset.py \
  --num-examples 120 \
  --output-dir data/qlora_usecases
```

Outputs:
- `data/qlora_usecases/train.jsonl`
- `data/qlora_usecases/eval.jsonl`
- `data/qlora_usecases/all_examples.jsonl`
- `data/qlora_usecases/summary.json`

### 2) Train QLoRA Adapter

```bash
cd backend
uv run python scripts/train_qlora_on_usecases.py \
  --train-file data/qlora_usecases/train.jsonl \
  --eval-file data/qlora_usecases/eval.jsonl \
  --model-id models/medgemma-1.5-4b-it \
  --output-dir artifacts/qlora_usecase_run
```

Notes:
- 4-bit QLoRA requires CUDA (`--no-use-4bit` for non-CUDA fallback).
- Adapter weights are saved under `artifacts/qlora_usecase_run/adapter`.

### 3) Evaluate Baseline vs QLoRA

```bash
cd backend
uv run python scripts/evaluate_baseline_vs_qlora.py \
  --eval-file data/qlora_usecases/eval.jsonl \
  --model-id models/medgemma-1.5-4b-it \
  --adapter-dir artifacts/qlora_usecase_run/adapter \
  --output-dir artifacts/qlora_usecase_run/eval_compare
```

Outputs:
- `artifacts/qlora_usecase_run/eval_compare/metrics_summary.json`
- `artifacts/qlora_usecase_run/eval_compare/predictions.jsonl`
- `artifacts/qlora_usecase_run/eval_compare/report.md`

### 4) Run Hallucination Regression Gate

Use this gate to fail when hallucination-focused metrics fall below minimums or
regress against a stored baseline run.

```bash
cd backend
uv run python scripts/hallucination_regression_gate.py \
  --candidate-metrics artifacts/qlora_usecase_run/eval_compare/metrics_summary.json \
  --candidate-scope baseline \
  --baseline-metrics artifacts/hallucination_eval/baseline_metrics_summary.json \
  --baseline-scope baseline \
  --output-json artifacts/hallucination_eval/gate_report.json
```

Notes:
- `--baseline-metrics` is optional; if omitted, only absolute thresholds are enforced.
- Use `--candidate-scope finetuned` to gate tuned-model quality instead of baseline.
- `--warn-only` returns exit code `0` while still printing failures (dry-run mode).
- Use `--min-candidate-examples` and `--min-baseline-examples` to reject tiny eval runs.
- Use `--min-task-policy-pass-rate task=value` to enforce task-specific pass rates.
- Use `--min-task-examples task=value` to enforce task coverage by category.
- CI default baseline snapshot: `data/hallucination_eval/baseline_metrics_summary.json` (22 examples).
- Baseline update policy: `data/hallucination_eval/BASELINE_POLICY.md`.

### 5) Refresh RAG Hallucination Baseline Snapshot

This path is lightweight and CI-safe because it evaluates deterministic
guardrail behavior instead of running large model inference.

```bash
cd backend
uv run python scripts/evaluate_rag_hallucination.py \
  --eval-file data/hallucination_rag_eval/eval.jsonl \
  --output-dir artifacts/hallucination_eval/current \
  --scope baseline \
  --min-policy-pass-rate 1.0
cp artifacts/hallucination_eval/current/metrics_summary.json \
  data/hallucination_eval/baseline_metrics_summary.json
```

### 6) Real MedGemma Runtime Smoke (Non-Mock)

Use this when you want to verify actual local model inference, not only guardrail
helpers with mocked/stubbed LLM behavior.

```bash
cd backend
RUN_REAL_MEDGEMMA_INFERENCE=1 uv run pytest tests/test_real_medgemma_inference.py -q
uv run python scripts/run_real_medgemma_smoke.py \
  --output-json artifacts/hallucination_eval/real_inference_smoke.json
```

### One-Command Orchestration

```bash
cd backend
uv run python scripts/run_qlora_experiment.py \
  --model-id models/medgemma-1.5-4b-it \
  --num-examples 120 \
  --output-root artifacts/qlora_experiment
```

Notes:
- On non-CUDA backends (MPS/CPU), the orchestrator automatically adds compatibility flags (`--no-use-4bit --no-bf16`) for both training and evaluation.
