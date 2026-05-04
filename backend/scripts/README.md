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

### 7) Speech Transcription Evaluation

Use this to benchmark the local MedASR runtime on real clips before changing
decoder settings, confidence thresholds, or transcript post-processing.

```bash
cd backend
uv run python scripts/evaluate_speech_transcription.py \
  --audio /absolute/path/to/patient-question.wav \
  --output-dir artifacts/speech_eval/current \
  --compare-plain-ctc
```

You can also pass a JSONL manifest with `audio_path`, `reference`, and optional `id`:

```bash
cd backend
uv run python scripts/evaluate_speech_transcription.py \
  --manifest data/speech_eval/manifest.jsonl \
  --output-dir artifacts/speech_eval/current
```

Outputs:
- `artifacts/speech_eval/current/summary.json`
- `artifacts/speech_eval/current/report.md`

### 8) Live Speech-to-Chat Smoke

Use this to verify the full local path:

1. login
2. `auth/me`
3. speech transcription
4. `chat/ask` with `input_mode=voice`

```bash
cd backend
uv run python scripts/run_speech_chat_smoke.py \
  --audio /absolute/path/to/patient-question.wav \
  --patient-id 10 \
  --output-json artifacts/speech_eval/live_smoke.json
```

Options:
- add `--skip-chat` to verify login + transcription only
- add `--question "..."` to override the transcript before `/chat/ask`
- add `--base-url http://localhost:8002` to point at a patched backend instance

Output:
- `artifacts/speech_eval/live_smoke.json`

### 9) Validate Human Speech Eval Manifest

Use this before running the MedASR eval on real human recordings:

```bash
cd backend
uv run python scripts/validate_speech_eval_manifest.py \
  --manifest data/speech_eval/human_en_v1/manifest.jsonl \
  --output-json artifacts/speech_eval/human_en_v1/manifest_summary.json
```

This checks:
- audio files exist
- references are present
- role / environment / speaker coverage can be summarized

### 10) Materialize WAXAL `swa_tts`

Download the Swahili TTS subset from Hugging Face and export normalized manifests:

```bash
cd backend
uv run --group finetune python scripts/materialize_waxal_swa_tts.py \
  --output-dir data/waxal_swa_tts
```

Outputs:
- `data/waxal_swa_tts/materialization_summary.json`
- `data/waxal_swa_tts/manifests/<split>.manifest.jsonl`
- `data/waxal_swa_tts/hf_cache/` (ignored in git)

### 11) Prepare the Swahili TTS Fine-Tune Job

Resolve the tracked fine-tune config against the local manifests:

```bash
cd backend
uv run python scripts/prepare_swa_tts_finetune.py \
  --config configs/speech/swa_tts_finetune_v1.json
```

Outputs:
- `artifacts/tts_finetune/swa_tts_v1/resolved_config.json`
- `artifacts/tts_finetune/swa_tts_v1/dataset_summary.json`

### 12) Stage or Execute the Swahili TTS Trainer Path

Stage the trainer workspace from the resolved WAXAL manifests:

```bash
cd backend
uv run python scripts/run_swa_tts_finetune.py \
  --config configs/speech/swa_tts_finetune_v1.json
```

This writes:
- `artifacts/tts_finetune/swa_tts_v1/trainer_workspace/launch_plan.json`
- `artifacts/tts_finetune/swa_tts_v1/trainer_workspace/run_external_trainer.sh`
- `artifacts/tts_finetune/swa_tts_v1/trainer_workspace/trainer.env`
- `artifacts/tts_finetune/swa_tts_v1/trainer_workspace/metadata_<split>.csv`

Run the configured external trainer adapter:

```bash
cd backend
uv run python scripts/run_swa_tts_finetune.py \
  --config configs/speech/swa_tts_finetune_v1.json \
  --execute
```

That command uses the tracked `trainer.command_template` to execute
`scripts/swa_tts_trainer_adapter.py`, which stages a concrete `coqui_vits`
backend workspace and validates the trainer inputs end to end.

To run a real trainer, override `SWA_TTS_TRAINER_CMD` (or pass
`--trainer-command`) and execute the generated workspace script:

```bash
cd backend
SWA_TTS_TRAINER_CMD="python /opt/trainers/vits_trainer.py" \
  ./artifacts/tts_finetune/swa_tts_v1/trainer_workspace/run_external_trainer.sh
```

### 13) Release Deploy the Split TTS Worker

Use the release runbook in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/SPEECH_SERVICE_RELEASE_DEPLOYMENT.md`

This is the operational reference for:
- `SPEECH_SYNTHESIS_BACKEND=http`
- worker health checks
- rollout / rollback
- split-runtime release gates

One-command local release gate:

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory
./scripts/run_speech_service_release_gate.sh
```

### 14) Live Clinician Copilot Smoke

Use this to verify the clinician copilot v1 path end to end:

1. clinician signup/login
2. patient login
3. access request and grant reconciliation
4. bounded copilot run creation
5. run listing and single-run fetch

```bash
cd backend
python scripts/run_clinician_copilot_smoke.py \
  --template chart_review \
  --output-json artifacts/clinician_copilot/live_smoke.json
```

Options:
- add `--patient-id 10` to force a specific patient
- add `--template data_quality` to verify a different bounded flow
- add `--base-url http://localhost:8002` to point at another backend instance

Behavior:
- if the demo patient account does not exist yet, the smoke script signs it up first
- if the demo patient has no patient rows yet, the smoke script creates the first patient record before continuing

Output:
- `artifacts/clinician_copilot/live_smoke.json`

One-command wrapper from the repo root:

```bash
./scripts/run_clinician_copilot_demo_check.sh
```

Useful options:
- `--template data_quality` to exercise a different bounded path
- `--backend-url http://localhost:8002` to point at another API instance
- `--frontend-url http://localhost:4173` to point Playwright at a non-default UI
- `--restart-frontend` to restart the local `frontend` dev service on `:5173` before Playwright
- `--skip-browser` or `--skip-backend` when isolating failures

Loopback note:
- if the backend URL uses `localhost` and `http://127.0.0.1:8000/health` is reachable, the wrapper automatically switches to the IPv4 loopback URL before running the smoke checks
- before Playwright runs, the wrapper validates that the frontend URL serves the MedMemory app shell; if the local UI is stale or down, rerun with `--restart-frontend`

CI note:
- the same gate now runs in GitHub Actions via:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`

### 15) Prepare a Fresh CI/Staging Database

Use this when local CI or staging needs a ready schema on an empty database:

```bash
cd backend
python scripts/ensure_schema_ready.py
```

Behavior:
- empty database:
  - create the current schema from application models
  - stamp Alembic to head
- existing versioned database:
  - run Alembic upgrade to head
- existing unversioned non-empty database:
  - fail fast instead of silently stamping drift

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
