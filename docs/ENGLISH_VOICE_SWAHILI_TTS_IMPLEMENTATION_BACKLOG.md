# MedMemory Implementation Backlog: English Voice + Swahili Text and TTS

Derived from:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/ENGLISH_VOICE_SWAHILI_TTS_PRODUCTION_PLAN.md`

This document converts the production strategy into a delivery backlog. It is organized by phase and split into:

- **backend API tasks**
- **frontend flow tasks**
- **infra/model/data tasks**
- **acceptance gates**

The goal is to ship:

1. **English voice input** for patient and clinician chat using MedASR
2. **Swahili patient text chat**
3. **Swahili production TTS replies**

Non-goals for this backlog:

- Swahili voice input
- clinician Swahili UI
- Kikuyu / Dholuo runtime support

---

## Status snapshot (March 12, 2026)

### Completed

- English voice input is live with local MedASR.
- Transcript review/edit before send is live.
- Patient and clinician English voice input paths are live.
- Swahili patient text chat is live.
- Swahili server-side TTS replies are live.
- Swahili TTS now has an extracted backend boundary (`in_process` or `http`) plus a dedicated internal service app entrypoint.
- The release runbook now exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/SPEECH_SERVICE_RELEASE_DEPLOYMENT.md`.
- Deterministic Swahili refusal/document-summary translations are live.
- Main CI and nightly both run the Swahili refusal smoke and upload isolated artifacts.
- A live browser speech-output smoke now exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/e2e/swahili-speech-output-smoke.spec.ts`.
- Main CI and nightly both run the Swahili speech-output smoke with isolated artifacts and dedicated worker/backend logs.
- `google/WaxalNLP` `swa_tts` is materialized locally under `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/data/waxal_swa_tts` with normalized manifests.
- The first Swahili TTS fine-tune config exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/configs/speech/swa_tts_finetune_v1.json`.
- The dataset prep/validation entrypoint exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/prepare_swa_tts_finetune.py`.
- The first trainer execution entrypoint exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/run_swa_tts_finetune.py`.
- The tracked backend adapter exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/swa_tts_trainer_adapter.py`.
- The local release gate exists at `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh`.

### In progress / partially complete

- MedASR quality hardening is underway; the real-human eval scaffold exists, but recordings still need to be captured.
- Dedicated TTS deployment is partially hardened; local compose/CI and the local release gate can run `SPEECH_SYNTHESIS_BACKEND=http`, but environment-specific deployment automation is not wired yet.
- Swahili TTS training prep is partially complete; manifests resolve, trainer workspaces are generated, and the `coqui_vits` adapter prepares backend-specific filelists, but actual backend training execution is still disabled.

### Not started

- WAXAL-based Swahili TTS fine-tuning job
- production speech metrics dashboards
- English TTS
- Swahili ASR

---

## Phase 0 — Contracts, service boundaries, and artifact management

### Objective

Stabilize the interfaces before adding speech services so the chat core does not get rewritten later.

### Backend API tasks

- [x] Add speech-aware request/response metadata to `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/schemas/chat.py`
  - `input_mode: text | voice`
  - `response_mode: text | speech | both`
  - `audio_asset_id`
  - `audio_url`
  - `audio_duration_ms`
  - `transcript_confidence`
- [x] Keep `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/chat.py` focused on orchestration only
  - no direct model loading
  - no raw audio parsing
  - no TTS generation logic inside chat handlers
- [x] Create `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/speech.py`
  - own router for speech endpoints
  - clean separation from chat routes
- [x] Create `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/`
  - `transcribe.py`
  - `synthesize.py`
  - `storage.py`
  - `validators.py`
- [x] Extract `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/synthesis_boundary.py`
  - `in_process` mode for the main backend
  - `http` mode for a dedicated TTS runtime
- [x] Create `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/speech_service.py`
  - internal synthesize endpoint
  - internal readiness endpoint
  - optional shared-secret auth

### Frontend flow tasks

- [x] Extend `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/types.ts` for voice/transcript/audio metadata
- [x] Extend `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/api.ts`
  - add speech endpoint clients
  - keep chat endpoint clients unchanged where possible
- [x] Add `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useSpeech.ts`
  - microphone capture state
  - upload state
  - transcript review state
  - playback state
- [x] Keep `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useChat.ts` as the single text-chat source of truth

### Infra/model/data tasks

- [ ] Define internal artifact layout
  - `/opt/medmemory/models/medasr/<revision>/`
  - `/opt/medmemory/models/swahili-tts/<revision>/`
  - `/opt/medmemory/datasets/waxal/<revision>/`
- [ ] Add a provisioning path for Hugging Face downloads
  - revision-pinned
  - checksum-verified
  - mirrored locally
- [ ] Define model version metadata format
  - source repo/model id
  - revision
  - checksum
  - created_at

### Acceptance gate

- [x] Chat API contracts can represent text-only, voice-in, and speech-out flows without breaking existing consumers
- [x] No speech model code is loaded inside existing chat handlers

---

## Phase 1 — English voice input with MedASR

### Objective

Ship safe English voice input for both patient and clinician chat without changing the reasoning core.

### Backend API tasks

- [x] Implement `POST /api/v1/speech/transcribe` in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/speech.py`
  - multipart audio upload
  - optional `patient_id`
  - optional `clinician_mode`
  - returns transcript + confidence + language
- [x] Implement MedASR wrapper in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/transcribe.py`
  - local checkpoint loading from Hugging Face mirror
  - warm start / singleton model management
  - structured result object
- [x] Add transcript validation in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/validators.py`
  - reject empty transcript
  - confidence threshold
  - max audio length
  - English-only gating
- [x] Add request auditing
  - transcript confidence
  - latency
  - transcript edit required

### Frontend flow tasks

- [x] Add microphone trigger to `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/ChatInterface.tsx`
  - English lane only
  - hidden for unsupported language/context
- [x] Build transcript review UI in `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useSpeech.ts`
  - show recognized text
  - allow user edit
  - require explicit submit
- [x] Integrate transcript -> chat send in `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useChat.ts`
  - transcript becomes normal chat input
  - preserve `input_mode=voice`
- [x] Enable for both patient and clinician English chat flows

### Infra/model/data tasks

- [x] Download `google/medasr` locally from Hugging Face during provisioning
- [ ] Define transcribe service runtime
  - GPU preferred
  - CPU fallback sizing documented
- [x] Add service health check
  - model loaded
  - inference ready
- [x] Route public speech/chat callers through the TTS boundary instead of the local runtime directly
- [x] Add request limits
  - max upload size
  - max duration
  - timeout

### Acceptance gate

- [x] Patient can ask an English question by voice, edit transcript, and submit
- [x] Clinician can do the same in clinician mode
- [x] Failed transcription never auto-submits
- [x] Existing text chat remains unchanged

---

## Phase 2 — Swahili patient text lane hardening

### Objective

Make the Swahili typed-chat path production-safe before adding speech output.

### Backend API tasks

- [x] Harden `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/multilingual.py`
  - keep `en` and `sw` only
  - explicit language capability registry
  - glossary enforcement hooks
- [x] Add translation output validation
  - preserve numbers
  - preserve units
  - preserve medication names
  - preserve dates
  - preserve source labels
  - preserve refusal language
- [x] Add translation failure fallback
  - return English answer only if translation fails
  - mark response metadata clearly

### Frontend flow tasks

- [x] Keep patient language selection in `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/utils/patientLanguage.ts`
  - `en`
  - `sw`
- [ ] Localize remaining patient-shell copy in:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/App.tsx`
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/dashboard/TrendsPanel.tsx`
- [x] Ensure translated response metadata is visible to the UI
  - `input_language`
  - `output_language`
  - `translation_applied`
- [ ] Add failure UI for translation fallback
  - clear patient-facing messaging
  - no silent language switch

### Infra/model/data tasks

- [ ] Add translation telemetry
  - translation latency
  - failure rate
  - fallback rate
- [ ] Add regression fixtures for Swahili patient prompts
  - steps
  - heart rate
  - sleep
  - medication
  - refusal / no evidence

### Acceptance gate

- [x] Patient can type in Swahili and receive grounded Swahili text back
- [x] No grounding regressions versus English baseline
- [ ] Translation fallback behavior is explicit and safe

---

## Phase 3 — Swahili production TTS replies

### Objective

Replace browser-only Swahili playback with a production TTS service backed by a local model.

### Backend API tasks

- [x] Implement `POST /api/v1/speech/synthesize` in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/speech.py`
  - input: finalized Swahili text
  - output: audio asset metadata
- [x] Implement TTS wrapper in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/synthesize.py`
  - load local `facebook/mms-tts-swh` derived checkpoint
  - expose deterministic inference interface
- [x] Implement audio storage in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/storage.py`
  - local or object-store backed
  - version-aware cache key
- [x] Gate TTS strictly
  - Swahili only
  - patient mode only in v1
  - final answer only

### Frontend flow tasks

- [x] Replace direct browser-only Swahili playback path in `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/ChatInterface.tsx`
  - use server-generated audio for Swahili replies
  - keep browser playback API only as player
- [x] Add auto-play toggle for patient Swahili replies
- [x] Add loading and retry states for TTS generation
- [x] Show audio availability per message

### Infra/model/data tasks

- [x] Download `facebook/mms-tts-swh` locally from Hugging Face
- [x] Download `google/WaxalNLP` locally and materialize `swa_tts`
- [ ] Build fine-tuning pipeline
  - [x] split generation
  - [x] training config versioning
  - [x] dataset summary / manifest validation
  - [x] trainer workspace staging
  - [x] mock execution path
  - [ ] text normalization
  - [ ] pronunciation cleaning
  - [ ] real trainer execution
- [ ] Register TTS model versions
  - base model revision
  - fine-tune dataset revision
  - training run id
  - checksum
- [ ] Add synthesis service deployment
  - [x] own container
  - [x] own health endpoint
  - [x] local release gate
  - own autoscaling rules if needed

### Quality tasks

- [ ] Evaluate pronunciation of:
  - numbers
  - dates
  - medication names
  - units
  - common Swahili medical guidance phrases
- [ ] Approve one canonical production voice
- [ ] Reject models with unstable pronunciation or clipping

### Acceptance gate

- [x] Patient receives a Swahili text answer and a matching Swahili audio reply
- [x] TTS output is generated only after the final grounded text answer exists
- [x] Audio cache works and repeated playback does not re-synthesize unnecessarily

---

## Phase 4 — Production hardening and rollout

### Objective

Turn the speech stack from a feature into an operable production subsystem.

### Backend API tasks

- [ ] Add feature flags
  - English voice input enabled
  - Swahili TTS enabled
- [ ] Add quota/rate-limit protection for speech endpoints
- [ ] Add structured speech error codes
- [ ] Add end-to-end audit events for speech flows

### Frontend flow tasks

- [ ] Add recovery UX
  - recording failed
  - upload failed
  - transcript low confidence
  - synthesis failed
- [ ] Add accessibility polish
  - keyboard support
  - clear button states
  - reduced-motion friendly audio state changes
- [ ] Add admin/testing toggles only in non-production environments

### Infra/model/data tasks

- [x] Add CI/nightly regression guards for Swahili refusal flows
  - main CI isolated artifact upload
  - nightly isolated artifact upload
- [x] Add CI/nightly regression guards for Swahili speech output
  - main CI isolated artifact upload
  - nightly isolated artifact upload
- [ ] Add dashboards
  - ASR latency
  - ASR confidence
  - transcript edit rate
  - TTS latency
  - TTS cache hit rate
  - translation failure rate
- [ ] Define rollback plan per model version
- [ ] Define backup/retention policy for cached audio
- [ ] Ensure no raw audio persistence by default

### Acceptance gate

- [ ] Service can roll forward/back per model version without code redeploy
- [ ] Monitoring covers all speech-critical failure points
- [ ] No raw audio is stored by default in production

---

## Phase 5 — Deferred backlog

These are intentionally **not** part of the current production path:

- [ ] Swahili ASR
- [ ] English production TTS service
- [ ] multi-voice Swahili selection
- [ ] clinician Swahili UI
- [ ] speaker identification

---

## Cross-phase testing backlog

### Backend

- [ ] add schema tests for speech metadata
- [ ] add transcribe endpoint tests
- [ ] add synthesize endpoint tests
- [ ] add translation validation tests
- [ ] add cache-key correctness tests

### Frontend

- [ ] add transcript review interaction tests
- [ ] add microphone failure tests
- [ ] add Swahili audio playback tests
- [ ] add feature-flag visibility tests

### End-to-end

- [ ] patient English voice -> transcript review -> grounded answer
- [ ] clinician English voice -> transcript review -> grounded answer
- [ ] patient Swahili text -> translated grounded answer -> Swahili audio
- [x] patient Swahili refusal smoke in CI and nightly

---

## Suggested delivery order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4

Do not start Swahili production TTS before:

- the Swahili text path is stable
- the artifact pipeline is in place
- model versioning is defined

Do not start Swahili ASR in parallel. It is a different problem and should stay out of the critical path for this release.

---

## Immediate next steps

1. Record the first `human_en_v1` MedASR eval clips and publish the first benchmark report.
2. Enable actual backend training execution inside `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/swa_tts_trainer_adapter.py`.
3. Add speech telemetry dashboards and alert thresholds.
4. Thread ASR confidence/edit-rate through the API response and analytics pipeline.
5. Promote `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh` into environment-specific deploy automation.
