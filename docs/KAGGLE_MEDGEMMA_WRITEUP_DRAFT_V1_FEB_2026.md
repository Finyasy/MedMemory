# MedMemory - Kaggle Writeup Draft v1 (MedGemma Impact Challenge)

Draft date: February 23, 2026  
Status: Pre-filled draft for Kaggle Writeup (replace placeholders before submission)

## Project name
MedMemory: A Patient-Controlled, Evidence-Grounded Health Record Copilot with MedGemma

## Your team
- [Your Name] - Product / Full-stack engineering - Built MedMemory backend/frontend, workflow UX, and evaluation tooling.
- [Teammate Name or "Solo Project"] - [Role] - [Specific contributions]

## Problem statement
Healthcare records are fragmented across hospital portals, lab vendors, imaging systems, and PDFs. Patients and clinicians often need quick answers (for example: "What was the latest LDL?", "What changed since last visit?", or "Is there a documented value for X?"), but current AI assistants frequently answer without enough patient-specific context, which can create unsafe or misleading outputs.

This creates two linked problems:
- Access problem: the relevant information is scattered across disconnected sources.
- Trust problem: even when an LLM is available, it may hallucinate or infer beyond the record.

MedMemory addresses this by consolidating records into a patient-controlled workspace and using MedGemma for grounded, local-first question answering with explicit refusal behavior when evidence is missing. The target users are:
- Patients trying to understand their own labs, medications, and reports in plain language.
- Clinicians reviewing chart context quickly using a focused, technical assistant tied to approved patient records.

If deployed in practice, this can improve workflow efficiency and reduce error-prone chart navigation while increasing trust in AI-assisted explanations by requiring evidence-backed responses.

## Overall solution
We built MedMemory, a full-stack medical record assistant that uses Google MedGemma (`google/medgemma-1.5-4b-it`) as the core local model for grounded Q&A, structured summarization, OCR refinement, and vision chat, while enforcing fail-closed guardrails and source transparency.

### How we use HAI-DEF / MedGemma
MedGemma is used in the following product paths:
- Grounded patient Q&A over retrieved records (`/api/v1/chat/ask`)
- Structured summary generation (JSON-first path with friendly rendering)
- Clinician-mode chart chat (terse, citation-aware responses)
- OCR refinement of extracted medical text from documents
- Vision chat for medical images (e.g., chest X-ray prompts)

This is a strong fit for HAI-DEF because the product requires:
- Medical-language understanding
- Local/offline-capable deployment options (important for privacy-constrained settings)
- Customizable infrastructure and guardrails (rather than relying on a closed hosted model)

### Human-centered design principle
Our design goal is not just "answer more questions," but to answer safely:
- Use retrieved patient-specific evidence when available
- Cite sources and preserve traceability
- Refuse unsupported claims with a consistent message (e.g., "I do not know from the available records.")

## Technical details

### Architecture and product stack
MedMemory is a full-stack application with:
- Backend: FastAPI + Pydantic + service-layer architecture (`backend/app/*`)
- Frontend: React + TypeScript + Vite (`frontend/src/*`)
- Data layer: PostgreSQL + `pgvector` for memory chunks / local retrieval
- Deployment modes:
  - Docker Compose (full stack)
  - Hybrid local backend + Docker DB/frontend (recommended for Apple Silicon / M4)

Relevant implementation areas in this repository:
- RAG orchestration: `backend/app/services/llm/rag.py`
- Retrieval + ranking: `backend/app/services/context/retriever.py`
- Cross-encoder reranking (second stage): `backend/app/services/context/cross_encoder_reranker.py`
- Evidence validation / numeric claim checks: `backend/app/services/llm/evidence_validator.py`
- LLM runtime + Apple Silicon runtime selection (MLX + Transformers fallback): `backend/app/services/llm/model.py`
- Decoding and grounding config: `backend/app/config.py`

### Grounding and hallucination mitigation
We focused on reducing hallucinations by combining retrieval, guardrails, and deterministic decoding:

1. Retrieval-Augmented Generation (RAG)
- Patient-specific retrieval is performed before generation.
- Structured search is used for factual/list/value-like queries when appropriate.
- Cross-encoder reranking is available to improve precision on top candidates.

2. Fail-closed grounding policy
- Strict factual intents (e.g., values/status/list queries) can be refused before generation when evidence is missing or weak.
- The system uses a canonical refusal path instead of speculative completion.

3. Numeric claim grounding and citation checks
- Numeric claims are validated against retrieved context.
- Unsupported numeric claims are removed or refused based on policy.
- Clinician mode can enforce inline citations for numeric claims.

4. Structured outputs for summary workflows
- The backend supports structured summary generation (`ask_structured`) with schema validation.
- The frontend preserves and renders `structured_data` and `sources` in chat responses.

5. Deterministic runtime defaults
- Text generation is configured toward deterministic behavior (`do_sample=false` for core text paths).
- Runtime decoding settings are surfaced through the LLM info endpoint to make behavior inspectable.

### Apple Silicon / local runtime feasibility (MacBook Pro M4, 24GB RAM)
MedMemory supports a hybrid local-first setup where the backend and MedGemma run locally while the DB/frontend can remain containerized. This is practical for an Apple Silicon development machine and supports privacy-focused prototyping.

Important implementation notes:
- The codebase includes an MLX text backend path for Apple Silicon and a Transformers fallback path.
- Runtime selection and quantization preferences are configurable in `backend/app/config.py`.
- A hybrid setup is documented in `README.md` and `backend/README.md`.

This makes the project feasible for local development, demos, and privacy-first workflows without requiring a permanently online hosted model.

### User-facing workflows implemented
1. Patient workflow
- Connect/upload records
- Ask plain-language questions
- Receive grounded responses with source references
- Review structured summaries and highlighted trends

2. Clinician workflow
- Clinician login + dashboard queue
- Link/request patient access
- Open approved patient workspace
- Ask technical chart questions in a focused interface with citations/sources

We also refactored the frontend into reusable dashboard components (e.g., connections, highlights, trends, focus areas) and added Playwright smoke coverage for dashboard flows:
- Playwright smoke test: `frontend/e2e/dashboard-smoke.spec.ts`

### Evaluation methodology (current)
We created a hallucination-focused RAG regression evaluation and gating workflow:
- Regression evaluation: `backend/scripts/evaluate_rag_hallucination.py`
- Regression gate / non-regression thresholds: `backend/scripts/hallucination_regression_gate.py`

The evaluation includes task buckets such as:
- `numeric_grounding`
- `numeric_citation`
- `context_gate`
- question/summary/trend-style tasks (depending on eval set configuration)

Metrics supported by the pipeline include:
- `hallucination_rate`
- `fact_precision`
- `fact_recall`
- `token_f1`
- `policy_pass_rate`

Latest local gate snapshot available in repo artifacts (for draft reference):
- Artifact date: 2026-02-16 (`backend/artifacts/hallucination_eval/gate_report.json`)
- Eval file: `data/hallucination_rag_eval/eval.jsonl`
- Sample size: 22 examples
- Gate status: PASS

Automation support also exists for rollout checks:
- `scripts/automate_hallucination_next_steps.sh`

### Results (fill with final frozen metrics)
The table below is pre-filled from the latest local draft artifacts. Replace with your final frozen submission run if you re-run evaluation before recording the video.

| Metric | Baseline | Final (Current) | Notes |
|---|---:|---:|---|
| Hallucination rate | 0.00 | 0.00 | `n=22`, local regression eval snapshot |
| Fact precision | 1.00 | 1.00 | `n=22`, local regression eval snapshot |
| Fact recall | 1.00 | 1.00 | `n=22`, local regression eval snapshot |
| Token F1 | 1.00 | 1.00 | `n=22`, local regression eval snapshot |
| Policy pass rate | 1.00 | 1.00 | Overall and per-task in current gate snapshot |
| p50 latency (patient Q&A) | [fill] | [fill] | End-to-end |
| p50 latency (clinician chat) | [fill] | [fill] | End-to-end |

Per-task policy pass rates in the latest gate snapshot (all passed):
- `context_gate` (n=5): 1.00
- `numeric_citation` (n=4): 1.00
- `numeric_grounding` (n=4): 1.00
- `question_mode` (n=4): 1.00
- `trend_direct` (n=5): 1.00

### Product feasibility
This project is designed as a real product prototype rather than a benchmark-only demo:
- Full UI for both patient and clinician workflows
- Local-first / hybrid runtime modes
- Reproducible backend scripts for evaluation and regression gates
- Explicit operational controls for decoding and grounding policies
- Extensible provider sync and document ingestion pathways

Known limitations (transparent disclosure):
- Some automated tests validate guardrail logic with stubs/mocks rather than full MedGemma inference in every path.
- Real local inference behavior depends on hardware/runtime availability (MLX/Transformers setup, model download, memory pressure).
- The current hallucination regression set is small (`n=22`) and should be expanded with more real failure cases for stronger external validity.
- Clinical use requires additional validation, privacy/compliance hardening, and workflow integration testing before production deployment.

### Impact estimate (fill with your current numbers)
We estimate MedMemory can improve user workflows in two ways:
- Faster chart-context retrieval and summarization for clinicians
- More trustworthy patient-facing explanations through evidence-gated responses

Planned/observed impact metrics:
- Time-to-answer reduction for common record questions: [fill]
- Reduction in unsupported responses on eval set: [fill]
- Increase in source-cited responses for high-risk numeric claims: [fill]

### Why this is a strong fit for the Agentic Workflow Prize (recommended special track)
MedMemory reimagines a multi-step, high-friction workflow as a coordinated system:
- retrieve records
- analyze question intent
- fetch and rerank evidence
- enforce grounding policy
- generate response with MedGemma
- validate numeric claims and citations
- present structured, user-specific output in patient/clinician UI

This is not only a chatbot. It is a tool-driven workflow assistant with explicit safety and evidence steps around the model.

### Links
- Video (required): [ADD URL]
- Public code repository (required): [ADD URL]
- Live demo (optional): [ADD URL]
- Additional evaluation artifacts (optional): [ADD URL]

## Appendix (optional notes for final version, remove if space is tight)

### Reproducibility pointers
- Backend setup and hybrid local run instructions: `README.md`, `backend/README.md`
- Model download helper: `backend/scripts/download_model.py`
- Real MedGemma smoke script: `backend/scripts/run_real_medgemma_smoke.py`
- Hallucination regression evaluation + gating:
  - `backend/scripts/evaluate_rag_hallucination.py`
  - `backend/scripts/hallucination_regression_gate.py`

### Submission polish tips before final Kaggle upload
- Replace all `[fill]` placeholders with frozen metrics and concrete impact estimates.
- Keep the final writeup concise (Kaggle limit is 3 pages).
- Align terminology with the video (same metric names, same workflow names).
- Include one architecture diagram and one workflow screenshot for clarity.
