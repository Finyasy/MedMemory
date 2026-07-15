# Hallucination Reduction Plan (Feb 2025 Ideas, Mapped to MedMemory)

Date: February 13, 2026  
Owner: MedMemory backend/frontend  
Scope: `backend/app/services/llm/*`, `backend/app/services/context/*`, `frontend/src/*`

## Goal

Reduce hallucinations by making answers fail closed unless evidence exists in retrieved records, while keeping local performance acceptable on a MacBook Pro M4 (24GB RAM).

## Current State (Already in Your App)

1. RAG is already implemented with local retrieval and grounding:
- `backend/app/services/llm/rag.py`
- `backend/app/services/context/engine.py`
- `backend/app/services/context/retriever.py`

2. Local vector DB is already present via PostgreSQL + `pgvector` (not Chroma/Pinecone):
- `backend/app/models/memory_chunk.py`

3. Evidence guardrails already exist:
- `backend/app/services/llm/evidence_validator.py`

4. Text chat generation is already mostly deterministic:
- `backend/app/services/llm/model.py` uses `do_sample=False` by default for text generation.

5. Structured output path exists but is not fully wired in frontend flow:
- Backend: `RAGService.ask_structured()` in `backend/app/services/llm/rag.py`
- Frontend currently calls standard `chatAsk` without `structured=true` query flag.

## Gap Analysis vs Requested Ideas

### 1) RAG and strict grounding

Already present, but two gaps remain:
1. Retrieval fallback can still feed weak context into generation for some queries.
2. Grounding checks are partly post-generation regex cleanup instead of strict pre-generation refusal.

### 2) Inference parameters

Text path is deterministic already. Gaps:
1. Config still defaults to `LLM_TEMPERATURE=0.7` (misleading when sampling is off).
2. Some multimodal endpoints still sample (`/chat/cxr/compare` uses `do_sample=True`, `temperature=0.35`, `top_p=0.9`).
3. `top_k` is not configurable.

### 3) Prompting techniques

Strong prompts exist, but:
1. Few-shot grounded examples are not consistently injected.
2. Structured output is optional and underused in normal UI flows.
3. "Think step-by-step" style prompting is not ideal for production medical UX; a hidden checklist plus evidence checks is safer.

### 4) Mac M4 local optimization

Important mismatch:
1. Current stack is Transformers model loading, not GGUF runtime.
2. Current 4-bit quantization path is CUDA-only; on MPS it is skipped.
3. So Q6_K/Q8_0 guidance applies only if adding an Ollama/LM Studio provider path.

### 5) Fine-tuning

You already have QLoRA scripts and eval tooling:
- `backend/scripts/train_qlora_on_usecases.py`
- `backend/scripts/evaluate_baseline_vs_qlora.py`
- `backend/scripts/qlora_eval_utils.py`

Main caveat:
1. 4-bit QLoRA requires CUDA; on Mac M4 it falls back to non-4bit modes and runs slower.

## Implementation Plan

## Phase 1: High Impact, Low Risk (Do First)

### P1-R1. Fail-closed grounding before generation

Applies to:
- `backend/app/services/llm/rag.py`
- `backend/app/services/context/retriever.py`
- `backend/app/config.py`

Requirements:
1. `LLM_STRICT_GROUNDING=true` must be default.
2. `LLM_MIN_RELEVANCE_SCORE` must be enforced before generation for factual intents.
3. `LLM_ALLOW_WEAK_FALLBACK=false` must remain default for factual intents.
4. `RAGService.ask()` and `stream_ask()` must refuse and skip generation when factual evidence is insufficient.
5. Retriever fallback must stay disabled for `LIST`, `VALUE`, `STATUS` intents unless explicitly enabled.

Acceptance:
1. Factual low-evidence queries return refusal without calling generation.
2. Ask/stream regression tests validate refusal behavior.

### P1-R2. Deterministic decoding policy as explicit runtime contract

Applies to:
- `backend/app/config.py`
- `backend/app/services/llm/model.py`
- `backend/app/api/chat.py`
- `backend/app/schemas/chat.py`

Requirements:
1. Runtime config must expose and enforce `LLM_DO_SAMPLE`, `LLM_TOP_P`, `LLM_TOP_K`, and `LLM_REPETITION_PENALTY`.
2. High-stakes text endpoints must default to deterministic decoding.
3. `/api/v1/chat/llm/info` must report active decoding settings accurately.

Acceptance:
1. Runtime info endpoint matches effective generation settings.
2. No hidden sampling in clinical text flows.

### P1-R3. Structured output by default for summary workflows

Applies to:
- `backend/app/api/chat.py`
- `frontend/src/api.ts`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/api/generated/services/ChatService.ts`

Requirements:
1. Summary UI flows must call `/chat/ask?structured=true` by default.
2. Clinician mode must remain available via `/chat/ask?clinician_mode=true`.
3. UI must render `structured_data` and `sources` for transparency.

Acceptance:
1. Summary prompts resolve through structured mode.
2. Source metadata is visible in frontend responses.

## Phase 2: Grounding Quality Upgrades

### P2-R1. Numeric claim evidence and citation enforcement

Applies to:
- `backend/app/services/llm/rag.py`
- `backend/app/services/llm/evidence_validator.py`

Requirements:
1. Numeric claims must be grounded to retrieved evidence.
2. Citation auto-attach must only occur when source support is unambiguous.
3. Unverified numeric claims must be removed or refused per policy mode.

Acceptance:
1. No uncited numeric claims in clinician mode.
2. No fabricated numeric provenance from blanket source tags.

### P2-R2. Few-shot grounding templates for high-risk intents

Applies to:
- `backend/app/services/llm/rag.py`
- `backend/app/services/llm/prompt_examples_grounded.md`

Requirements:
1. Provide 3-5 strict grounded examples (evidence present, missing, conflicting).
2. Inject few-shot block selectively (factual/clinician-risk paths), not globally.
3. Templates must reinforce refusal and citation format consistency.

Acceptance:
1. Format drift is reduced in regression set.
2. Refusal behavior is more consistent across prompts.

## Phase 3: Mac M4 and Runtime Strategy

### P3-R1. Runtime and quantization policy for Apple Silicon

Applies to:
- `backend/app/services/llm/model.py`
- `backend/app/config.py`

Requirements:
1. MLX text backend should be preferred on Apple Silicon when available.
2. Transformers path must remain a functional fallback.
3. Token budgets should remain conservative on MPS/CPU to reduce instability.
4. Quantization guidance must remain runtime-specific:
- MLX quantization for MLX runtime.
- GGUF Q6_K/Q8_0 for Ollama/llama.cpp-style runtimes.
- bitsandbytes 4-bit remains CUDA-only in Transformers.

Acceptance:
1. Local M4 runs remain stable (no swap-driven regressions in normal workloads).
2. Runtime reporting reflects actual backend in use.

## Phase 4: Fine-Tuning and Evaluation Loop

### P4-R1. Hallucination-focused adaptation and gated rollout

Applies to:
- `backend/scripts/build_real_usecase_dataset.py`
- `backend/scripts/train_qlora_on_usecases.py`
- `backend/scripts/evaluate_baseline_vs_qlora.py`
- `backend/scripts/qlora_eval_utils.py`
- `backend/scripts/evaluate_rag_hallucination.py`
- `backend/scripts/hallucination_regression_gate.py`

Requirements:
1. Build eval sets from real failure cases (hallucinations + missing-evidence cases).
2. Train/evaluate adapters when appropriate for target environment.
3. Compare baseline vs tuned using hallucination-focused metrics.
4. Gate promotion on non-regression and task-level policy coverage.

Acceptance:
1. Candidate metrics pass absolute and regression thresholds before rollout.
2. Task coverage thresholds are met for required categories.

Notes:
1. CUDA remains preferred for QLoRA throughput; Mac fallback modes are slower.

## File-Level TODO Checklist

1. `backend/app/config.py`
- Add strict grounding and decoding controls.

2. `backend/app/services/context/retriever.py`
- Disable weak fallback for factual intents.

3. `backend/app/services/llm/rag.py`
- Fail closed before LLM call when evidence is insufficient.
- Add citation-required validation for numeric claims.
- Use few-shot strict grounded templates selectively.

4. `backend/app/services/llm/model.py`
- Wire config-driven `do_sample/top_p/top_k`.

5. `backend/app/api/chat.py`
- Keep deterministic defaults for clinical endpoints.
- Ensure structured and clinician query parameters are easy to consume.

6. `backend/app/schemas/chat.py`
- Extend `LLMInfoResponse` with decoding parameters.

7. `frontend/src/api.ts`
- Support `structured` and `clinician_mode` query flags for ask endpoint.

8. `frontend/src/hooks/useChat.ts`
- Use structured mode for summary prompts.
- Preserve source metadata in message state.

9. `frontend/src/components/*`
- Show citations/sources and confidence hints in answer UI.

10. `backend/tests/test_services_llm.py` and `backend/tests/test_chat_api.py`
- Add regression tests for refusal behavior, fallback suppression, and structured-mode routing.

## Validation Commands

From repo root:

```bash
cd backend
uv run pytest tests/test_services_llm.py tests/test_chat_api.py
```

Important:
1. The standard backend test suite primarily validates guardrail logic with stubs/mocks for LLM behavior.
2. Use the real-inference commands below to validate actual local MedGemma runtime execution.

Real MedGemma runtime smoke (non-mock, opt-in):

```bash
cd backend
RUN_REAL_MEDGEMMA_INFERENCE=1 uv run pytest tests/test_real_medgemma_inference.py -q
uv run python scripts/run_real_medgemma_smoke.py \
  --output-json artifacts/hallucination_eval/real_inference_smoke.json
```

Manual checks:

```bash
curl http://localhost:8000/api/v1/chat/llm/info -H "Authorization: Bearer <JWT>"
```

```bash
curl -X POST "http://localhost:8000/api/v1/chat/ask?structured=true&clinician_mode=true" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"patient_id":1,"question":"What is the latest hemoglobin value?"}'
```

QLoRA compare:

```bash
cd backend
uv run python scripts/evaluate_baseline_vs_qlora.py \
  --eval-file data/qlora_usecases/eval.jsonl \
  --model-id models/medgemma-1.5-4b-it \
  --adapter-dir artifacts/qlora_usecase_run/adapter \
  --output-dir artifacts/qlora_usecase_run/eval_compare
```

## Success Criteria

1. Hallucination rate decreases on eval set and real chat logs.
2. Factual questions with missing evidence return refusal text instead of speculative output.
3. Numeric claims are always source-grounded.
4. Deterministic mode is default for medical QA.
5. Frontend shows structured answers and source references for clinician workflows.


## Steps To Be Refined (Updated Feb 16, 2026)

This section replaces the draft notes above with implementation-ready requirements aligned to:
- This repository architecture (Transformers + optional MLX path + pgvector RAG).
- MedGemma 1.5 official model guidance and limitations.

### External constraints from MedGemma 1.5 docs (must be reflected in design)

1. MedGemma is intended as a starting point and requires downstream adaptation/validation for specific use cases.
2. Outputs are preliminary and not for direct clinical decision-making without independent verification.
3. Multimodal performance has primarily been evaluated on single-image tasks.
4. The model is not evaluated/optimized for multi-turn behavior and is prompt-sensitive.
5. MedGemma 1.5 4B supports long context (up to 128K tokens) and 8192-token output, but practical local limits still apply.

### Refined requirements

#### R1. Grounding and refusal policy (must)

1. Every factual answer (`LIST`, `VALUE`, `STATUS`) must be evidence-grounded before generation.
2. If evidence is missing or below threshold, the service must fail closed and skip generation.
3. Weak fallback retrieval must remain disabled for factual intents unless explicitly enabled by config.
4. Low-confidence inference text, when enabled, must be clearly labeled as low confidence and never presented as fact.

Acceptance:
1. Factual unsupported queries return refusal with no LLM generation call.
2. Regression tests cover ask + stream paths.

#### R2. Numeric claim controls (must)

1. Numeric claims must pass numeric grounding checks against retrieved context.
2. Auto-citation may only be attached when exactly one source snippet supports the numeric tokens in that sentence.
3. If no unambiguous supporting source exists, do not auto-attach a citation; enforce citation policy afterward (clinician mode or global citation mode).

Acceptance:
1. No uncited numeric claims in clinician mode.
2. No fabricated provenance from blanket source tagging.

#### R3. Structured mode safety (must)

1. `ask_structured()` must always use grounded context (latest doc text or retrieved context), never a synthetic placeholder context.
2. If structured JSON is invalid after retries, return fail-closed refusal.
3. If structured validation fails after retries, return fail-closed refusal.
4. Structured responses must return sources metadata consistently.

Acceptance:
1. Structured no-evidence, invalid JSON, and validation-failure paths are covered by tests.
2. Frontend summary flow remains structured by default.

#### R4. Retrieval quality and reranking (must)

1. Keep two-stage retrieval: initial pgvector candidate set plus cross-encoder rerank.
2. Maintain candidate size 20 and strict factual top-k 3 defaults unless eval data justifies changes.
3. Factual answers should prioritize reranked high-confidence snippets; avoid noisy context expansion.

Acceptance:
1. Task-level hallucination gate remains at 1.0 pass rate for numeric grounding/citation/question mode/context gate/trend direct.

#### R5. Decoding policy (must/should)

1. Factual tasks must default to deterministic decoding (`do_sample=false`, temp 0 behavior).
2. Reasoning/summarization may use a bounded non-zero profile only when justified by eval and with grounding checks still enforced.
3. Production config must expose real decoding settings in `/api/v1/chat/llm/info`.

Acceptance:
1. No hidden sampling on high-stakes text endpoints.
2. Config and runtime info remain consistent.

#### R6. MedGemma-specific usage rules (must)

1. Avoid explicit chain-of-thought prompting in production responses; use internal guardrails + concise outputs.
2. Multi-image and longitudinal imaging flows should include stricter confidence language because official model evaluation is primarily single-image.
3. Multi-turn conversations must rely on explicit retrieved evidence each turn (do not rely on latent model memory).

Acceptance:
1. Prompt templates and clinician/patient modes reflect these constraints.

#### R7. Mac M4 runtime requirements (must/should)

1. Keep MLX text backend as preferred local runtime on Apple Silicon when available.
2. Keep Transformers fallback path healthy.
3. Keep token budgets conservative on MPS/CPU paths to avoid instability and swapping.
4. Keep quantization guidance runtime-specific:
- GGUF Q6_K/Q8_0 applies to Ollama/llama.cpp class runtimes.
- MLX quantization applies to MLX runtimes.
- bitsandbytes 4-bit remains CUDA-only in Transformers path.

Acceptance:
1. Local test/eval runs are stable on M4 without swap-driven regressions.

#### R8. Evaluation and release gate (must)

1. Keep hallucination regression evaluator + gate in CI and nightly workflows.
2. Gate on both aggregate metrics and task-level policy coverage.
3. Fail release on regression against baseline metrics.

Acceptance:
1. `artifacts/hallucination_eval/gate_report.json` is PASS in CI/nightly before merge.

### Additional improvements to schedule next

1. Add integration-style hallucination eval cases that execute full retrieval + prompt + generation path (not only helper-level checks).
2. Add explicit multi-turn robustness tests because MedGemma docs note it is not optimized for multi-turn.
3. Add endpoint-level policy for multi-image caution language in radiology comparison flows.

### References (official/primary)

1. MedGemma Hugging Face model card: https://huggingface.co/google/medgemma-1.5-4b-it
2. MedGemma repository (README + docs): https://github.com/Google-Health/medgemma
3. MedGemma 1.5 release notes: https://github.com/Google-Health/medgemma/blob/main/docs/release-notes.md
