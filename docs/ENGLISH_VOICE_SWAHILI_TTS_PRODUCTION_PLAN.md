# MedMemory Production Plan: English Voice Input + Swahili Text and TTS

## 0. Current implementation status (March 13, 2026)

### Implemented

- **English voice input is live** for patient and clinician chat using local `google/medasr`.
- **Transcript review is mandatory** before voice input becomes a chat message.
- **Swahili patient text chat is live** using the existing English RAG core plus translation in/out of English.
- **Swahili server-side TTS is live** using local `facebook/mms-tts-swh` assets.
- **Swahili TTS service boundary is live**:
  - main API calls `SpeechSynthesisBoundary`
  - boundary supports `in_process` and `http` modes
  - dedicated internal entrypoint exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/speech_service.py`
- **Release deployment runbook is published** at `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/SPEECH_SERVICE_RELEASE_DEPLOYMENT.md`
- **Deterministic Swahili fallbacks are live** for record refusals, latest-document refusals, trend summaries, Apple Health summaries, and common patient-facing document-summary variants.
- **Regression guards are live**:
  - main CI runs `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/e2e/swahili-refusal-smoke.spec.ts`
  - nightly tone workflow runs the same spec and uploads a dedicated artifact
- **Live browser speech smoke exists** at `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/e2e/swahili-speech-output-smoke.spec.ts`
  - verifies Swahili `response_mode=both`
  - verifies the split TTS boundary serves a generated speech asset
  - main CI and nightly both run it with isolated artifacts and dedicated worker/backend logs
- **WAXAL Swahili TTS data is materialized locally** under `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/data/waxal_swa_tts`
  - dataset SHA: `beab143ae6d8a5e054281241afd76565ecb57e03`
  - split counts: `train=1387`, `validation=192`, `test=199`

### Implemented locally, but not production-hardened

- MedASR assets are mirrored locally under the backend model path and loaded offline.
- `mms-tts-swh` assets are mirrored locally under the backend model path and loaded offline.
- KenLM-assisted MedASR decoding is wired, and the real-human eval scaffold exists under `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/data/speech_eval/human_en_v1`, but real recordings still need to be collected.
- Swahili TTS caching exists and the service boundary is extracted.
- The local release gate now exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh`, but release orchestration beyond local compose/CI still needs to be formalized.
- The first fine-tune prep path now exists:
  - config: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/configs/speech/swa_tts_finetune_v1.json`
  - prepare script: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/prepare_swa_tts_finetune.py`
  - generated outputs: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/artifacts/tts_finetune/swa_tts_v1`
- The first trainer execution boundary now exists:
  - runner: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/run_swa_tts_finetune.py`
  - staged workspace: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/artifacts/tts_finetune/swa_tts_v1/trainer_workspace`
  - current supported runtimes: `external_command`, `mock`
  - tracked backend adapter: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/swa_tts_trainer_adapter.py`

### Not implemented yet

- A real external Swahili TTS trainer runtime wired to the staged workspace
- Swahili TTS model version registry
- release-grade speech-service deployment automation beyond the current local release gate
- speech observability dashboards and quotas
- English TTS
- Swahili ASR

## 1. Decision summary

MedMemory should ship a two-lane language and speech architecture:

- **English lane**
  - **Voice input enabled**
  - shared by **patients and clinicians**
  - uses **MedASR** for speech-to-text
- **Swahili lane**
  - **text chat enabled**
  - patient-facing only in v1
  - responses translated back to Swahili
  - **Swahili TTS enabled for reply playback**
  - **no Swahili ASR in v1**

This is the best production shape because it matches the strengths of the available assets:

- **MedASR** is an English medical ASR model, not a TTS model
- **WAXAL** gives us a Swahili TTS data path
- **MedGemma** remains the grounded medical reasoning layer

The architecture keeps the existing English RAG core stable and adds speech/localization as composable services around it.

---

## 2. Product scope

### In scope

- English voice input for patient and clinician chat
- English text chat for patient and clinician chat
- Swahili text chat for patients
- Swahili spoken replies for patients
- Existing grounded MedGemma + retrieval flow remains the source of truth

### Out of scope for this release

- Swahili voice input
- Clinician Swahili workspace
- Kikuyu and Dholuo runtime support
- Speaker identification / voice biometrics
- Runtime downloads from GitHub

---

## 3. Core product architecture

Use four separate runtime components.

### A. `speech-transcribe` service

- Purpose: convert **English audio** to text
- Model: **MedASR**
- Input: microphone audio
- Output: transcript + confidence + timing metadata

### B. `patient-language` service

- Purpose: language normalization and translation for patient chat
- Handles:
  - `en -> en`
  - `sw -> en`
  - `en -> sw`
- Preserves:
  - numbers
  - units
  - medication names
  - dates
  - source labels
  - refusal statements

### C. `reasoning` service

- Purpose: current MedMemory medical reasoning stack
- Model: **MedGemma**
- Responsibilities:
  - retrieval
  - grounding
  - synthesis
  - refusal handling
  - clinician/patient mode guardrails

### D. `speech-synthesize` service

- Purpose: generate **Swahili audio replies**
- Model: dedicated **Swahili TTS production model**
- Input: finalized Swahili text answer
- Output: audio file/stream + duration + voice metadata
- Current implementation:
  - main API uses `SpeechSynthesisBoundary`
  - local runtime lives in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/synthesize.py`
  - dedicated service entrypoint lives in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/speech_service.py`

This separation is required. ASR, translation, reasoning, and TTS should not be combined into one process or one model abstraction.

---

## 4. Recommended model strategy

### 4.1 English ASR

- **Model**: MedASR
- **Use**: English voice input only
- **Do not use for**:
  - Swahili ASR
  - TTS
  - speaker voices

Why:

- the public MedASR materials position it as a medical **speech-to-text** model
- its model card states the training data is **English-only**
- this makes it appropriate for English patient/clinician dictation, but not for Swahili speech input

### 4.2 Medical reasoning

- **Model**: MedGemma
- **Use**:
  - grounded answer synthesis
  - patient/clinician response generation
  - existing RAG flow

This should remain unchanged. Speech is an I/O layer around the reasoning core, not a replacement for it.

### 4.3 Swahili TTS production model

Use a dedicated Swahili TTS model downloaded locally from Hugging Face and adapted with WAXAL Swahili TTS data.

**Recommended base model**

- **Base model**: `facebook/mms-tts-swh`
- **Model family**: **VITS**
- **Adaptation dataset**: `google/WaxalNLP` subset `swa_tts`

Why this is the right production choice:

- the base TTS checkpoint already exists on Hugging Face for Swahili
- it avoids training a Swahili reply voice from scratch
- VITS is efficient enough for production reply synthesis
- WAXAL `swa_tts` can be used to improve pronunciation, regional fluency, and medical-term stability

**Do not optimize for multiple voices first.**

For MedMemory v1, ship **one high-quality Swahili reply voice**. Add male/female voice selection only after quality, latency, and content safety are stable.

### 4.4 Translation layer

Keep translation as a separate service boundary from MedGemma reasoning.

- short term: reuse the current translation seam already added to the backend
- production expectation: enforce glossary-based post-validation and numerical consistency checks

This keeps the RAG core stable and makes future translation model swaps low-risk.

---

## 5. Official source and download strategy

### Important production rule

**Download models and datasets locally from Hugging Face during provisioning, not from GitHub at runtime.**

Hugging Face should be treated as the **artifact source**, and your internal model/data storage should be treated as the **runtime source**.

Production download flow should be:

1. pin exact Hugging Face model or dataset revision
2. download model/data locally during provisioning or CI
3. validate checksum and manifest
4. copy into internal model or data storage
5. serve from internal paths only

Recommended local pull method:

- `huggingface_hub.snapshot_download(...)` for models and datasets
- store under a versioned internal directory such as:
  - `/opt/medmemory/models/medasr/<revision>/`
  - `/opt/medmemory/models/swahili-tts/<revision>/`
  - `/opt/medmemory/datasets/waxal/<revision>/`

### Current local model paths in this repo

- MedASR: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/medasr`
- Swahili TTS: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/mms-tts-swh`

### Current dedicated TTS service entrypoint

- App entrypoint: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/speech_service.py`
- Boundary config:
  - `SPEECH_SYNTHESIS_BACKEND=in_process|http`
  - `SPEECH_SYNTHESIS_SERVICE_BASE_URL=http://127.0.0.1:8010`
  - `SPEECH_SYNTHESIS_SERVICE_TIMEOUT_SECONDS=30`
  - `SPEECH_SERVICE_INTERNAL_API_KEY=<shared-secret>`
- Example runtime command:
  - `cd /Users/bryan.bosire/anaconda_projects/MedMemory/backend && uv run uvicorn app.speech_service:app --host 127.0.0.1 --port 8010`

### Sources to pin

#### A. MedASR

- Hugging Face model: `https://huggingface.co/google/medasr`
- Official docs: `https://developers.google.com/health-ai-developer-foundations/medasr`

#### B. WAXAL speech data

- Hugging Face dataset: `https://huggingface.co/datasets/google/WaxalNLP`
- Research paper: `https://arxiv.org/pdf/2602.02734`
- GitHub project reference: `https://github.com/Waxal-Multilingual/speech-data`

#### C. Swahili TTS base model

- Hugging Face model: `https://huggingface.co/facebook/mms-tts-swh`

### Practical note about WAXAL

Use the Hugging Face dataset as the actual download source for data preparation. GitHub remains useful for project context and metadata, but production data pulls should be revision-pinned from Hugging Face and then mirrored internally.

---

## 6. How the product should work end to end

## 6.1 English voice input flow

### Patient or clinician asks in English by voice

1. browser records audio
2. frontend sends audio to `POST /api/v1/speech/transcribe`
3. `speech-transcribe` service runs MedASR
4. backend returns transcript + confidence
5. user can edit transcript before submit
6. existing text chat flow sends transcript into MedMemory
7. MedGemma + retrieval produce grounded answer
8. answer returns as text
9. optional English TTS can remain browser-based if needed

### Why transcript review is mandatory

- ASR errors should not silently become medical questions
- transcript review is a safety control, not a UX nicety

## 6.2 Swahili patient chat flow

### Patient types in Swahili

1. user sends Swahili text
2. `patient-language` service normalizes and translates to English
3. MedMemory runs the current English retrieval/reasoning flow
4. finalized answer is translated from English to Swahili
5. UI shows Swahili text response
6. if speech playback is enabled, `speech-synthesize` generates Swahili audio

### Important rule

The answer should be synthesized to speech **only after** the final grounded Swahili text is approved. Never synthesize intermediate drafts.

---

## 7. Concrete implementation plan by file and service

### 7.1 Backend

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/multilingual.py`

- keep as the translation/orchestration seam for now
- rename later to `patient_language.py`
- add capability registry:
  - `supports_translation`
  - `supports_tts`
  - `supports_asr`
- supported matrix should be:
  - `en`: translation false, TTS optional, ASR true
  - `sw`: translation true, TTS true, ASR false

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/chat.py`

- keep `POST /api/v1/chat/ask`
- keep `POST /api/v1/chat/stream`
- add speech-aware request metadata only where needed
- if `output_language == sw` and `response_mode` requires speech:
  - call `speech-synthesize` after final text answer

#### New route: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/speech.py`

Add:

- `POST /api/v1/speech/transcribe`
  - English audio only in v1
  - returns transcript + confidence
- `POST /api/v1/speech/synthesize`
  - Swahili text only in v1
  - returns audio asset metadata

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/schemas/chat.py`

Extend carefully with:

- `response_mode: text | speech | both`
- audio metadata:
  - `audio_asset_id`
  - `audio_url`
  - `audio_duration_ms`

Do not overload core answer fields with speech-specific state.

#### New service: `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/`

Split into:

- `transcribe.py`
  - MedASR inference wrapper
- `synthesize.py`
  - Swahili TTS inference wrapper
- `storage.py`
  - local/object storage for generated audio
- `validators.py`
  - language gating
  - transcript confidence checks
  - text normalization

### 7.2 Frontend

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/ChatInterface.tsx`

- remove direct speech runtime decisions from the component over time
- keep UI controls only:
  - microphone button for English lane
  - play audio button for Swahili replies

#### New hook: `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useSpeech.ts`

- microphone capture
- upload state
- transcript review state
- playback state
- failure and retry state

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useChat.ts`

- keep text chat source of truth
- add transcript review before converting voice input into a chat message
- attach `input_mode: text | voice`

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/utils/patientLanguage.ts`

- keep as the patient language capability registry
- only `en` and `sw`

#### `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/App.tsx`

- patient:
  - language preference
  - speech playback toggle
- clinician:
  - microphone enabled only for English voice input
  - no Swahili clinician lane in v1

---

## 8. Swahili TTS production model plan

### 8.1 Training plan

Use the following pipeline:

1. download `facebook/mms-tts-swh` locally from Hugging Face
2. download `google/WaxalNLP` locally and materialize the `swa_tts` subset
3. normalize text
4. clean punctuation and numerals for TTS pronunciation rules
5. create train/validation/test speaker-consistent splits
6. fine-tune the base VITS checkpoint on `swa_tts`
7. evaluate MOS-style listening quality, pronunciation, and latency
8. export the serving artifact
9. deploy as a dedicated TTS microservice

### 8.2 Production serving plan

- run TTS in its own service container
- keep model weights on local disk or mounted model volume
- cache generated audio by:
  - answer hash
  - language
  - voice id
  - model version

### 8.3 Quality gates

The Swahili TTS model is production-ready only if it passes:

- intelligibility of medical terms
- stable number/date reading
- low hallucination in pronunciations of units and medications
- acceptable latency for short answers
- no clipping or broken phonemes on long answers

### 8.4 Voice strategy

Start with:

- `sw_female_v1` **or**
- `sw_neutral_v1`

Do not start with multiple voices unless you have enough clean speaker-balanced data and explicit product need.

---

## 9. WAXAL `swa_tts` sizing

### Exact public numbers I found

- the public dataset viewer exposes a **`swa_tts` subset with about `1.78k` rows**
- the WAXAL paper reports the full **WAXAL-TTS** release at approximately:
  - **235 hours**
  - **17,660 instances**
  - **99 GB**

### What that means for planning

The public text I found does **not** give a clean exact `swa_tts` hour/GB figure in extracted text.

For production planning, the safe statement is:

- `swa_tts` is a **small-to-medium single-language TTS training subset**
- plan for **roughly one-digit to low-two-digit GBs** once mirrored locally
- verify the exact Swahili duration and storage footprint from the dataset manifest after download

### Working estimate

If the Swahili subset is close to the average TTS subset density, expect it to be on the order of:

- **~20–25 hours**
- **~8–12 GB**

Treat that as an **engineering estimate**, not a published exact figure.

---

## 10. Production operations

### Artifact management

- pin exact Hugging Face revision for each upstream artifact
- version every downloaded manifest
- checksum all model and dataset artifacts
- mirror everything into internal object or model storage
- never rely on live external downloads during application startup

### Security

- never store raw patient microphone audio by default
- store transcript, confidence, language, and request metadata
- store raw audio only for explicit debugging workflows

### Observability

Track separately:

- ASR latency
- ASR confidence distribution
- transcript edit rate
- translation failure rate
- TTS latency
- TTS cache hit rate
- answer grounding regressions

### Safety

- no auto-submit after transcription
- no speech synthesis before the grounded final answer exists
- preserve source labels and refusal language through translation

---

## 11. Rollout order

### Phase A

- finalize English + Swahili runtime cleanup
- keep current text chat stable

### Phase B

- add English voice input with MedASR
- patient and clinician transcript review

### Phase C

- add production Swahili TTS replies
- patient chat only

### Phase D

- harden metrics, caching, and model versioning
- run multilingual safety regression suite

Swahili ASR is intentionally deferred until a confirmed Swahili-capable ASR path is available and benchmarked.

---

## 11.1 Immediate next steps

These are the next production steps with the highest value-to-risk ratio:

1. **Record the first real-human MedASR benchmark pack**
   - populate `human_en_v1/manifest.jsonl`
   - capture patient and clinician audio
   - publish the first transcript-quality report
2. **Replace the adapter’s prepare-only path with real trainer execution**
   - use `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/configs/speech/swa_tts_finetune_v1.json`
   - use `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/run_swa_tts_finetune.py`
   - validate `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/artifacts/tts_finetune/swa_tts_v1/trainer_workspace/launch_plan.json`
   - define checkpoints and evaluation outputs
3. **Add speech observability**
   - ASR latency
   - ASR confidence
   - transcript edit rate
   - TTS latency
   - TTS cache hit rate
4. **Thread speech quality signals into product analytics**
   - ASR confidence in chat metadata
   - transcript edit distance / edit rate
   - synthesis cache utilization per locale
5. **Promote the speech-service release gate into deploy automation**
   - start from `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh`
   - add environment-specific deploy targets
   - keep rollback to `in_process`

---

## 12. Final recommendation

The production design should be:

- **MedASR** for **English voice input**
- **MedGemma** for **grounded medical reasoning**
- **translation service** for Swahili patient text in/out
- **dedicated Swahili TTS model** starting from `facebook/mms-tts-swh` and adapted with **WAXAL `swa_tts`**

That is the cleanest architecture because it uses each asset where it is strongest and avoids unsupported language or model paths in the runtime.

---

## 13. Source references and source-of-truth docs

Primary internal docs for this feature set:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/ENGLISH_VOICE_SWAHILI_TTS_PRODUCTION_PLAN.md`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/ENGLISH_VOICE_SWAHILI_TTS_IMPLEMENTATION_BACKLOG.md`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/swahili-medmemory-refactor-plan.md`

External references:

- MedASR overview: `https://developers.google.com/health-ai-developer-foundations/medasr`
- MedASR model card: `https://developers.google.com/health-ai-developer-foundations/medasr/model-card`
- MedASR Hugging Face model: `https://huggingface.co/google/medasr`
- WAXAL Google Research post: `https://research.google/blog/waxal-a-large-scale-open-resource-for-african-language-speech-technology/`
- WAXAL Africa blog post: `https://blog.google/intl/en-africa/company-news/outreach-and-initiatives/introducing-waxal-a-new-open-dataset-for-african-speech-technology/`
- WAXAL paper: `https://arxiv.org/pdf/2602.02734`
- WAXAL GitHub: `https://github.com/Waxal-Multilingual/speech-data`
- WAXAL dataset card: `https://huggingface.co/datasets/google/WaxalNLP`
- MMS Swahili TTS model: `https://huggingface.co/facebook/mms-tts-swh`
