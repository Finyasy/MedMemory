# MedMemory Swahili Refactor Plan

## Purpose

This document now serves as the **short refactor/status companion** to:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/ENGLISH_VOICE_SWAHILI_TTS_PRODUCTION_PLAN.md`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/ENGLISH_VOICE_SWAHILI_TTS_IMPLEMENTATION_BACKLOG.md`

The original three-language plan is no longer current. Runtime language support is intentionally limited to:

- `en` for patient and clinician chat
- `sw` for patient chat and patient speech output

Kikuyu and Dholuo are out of scope for the current product path.

---

## Current architecture

### Language lanes

- **English**
  - patient text chat
  - clinician text chat
  - patient voice input
  - clinician voice input
- **Swahili**
  - patient text chat
  - patient speech output

### Deliberate exclusions

- no Swahili ASR
- no clinician Swahili workspace
- no Kikuyu runtime
- no Dholuo runtime

---

## Refactor work completed

### Backend

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/multilingual.py`
  - narrowed to English/Swahili-only behavior
  - deterministic Swahili handling added for grounded answers, refusals, trend summaries, and latest-document refusal flows
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/chat.py`
  - language-aware ask/stream wiring
  - Swahili speech attachment after final answer generation
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/speech.py`
  - separate speech route surface for transcription and synthesis
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/speech/`
  - MedASR transcription
  - Swahili TTS synthesis
  - audio storage
  - validation helpers

### Frontend

- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/utils/patientLanguage.ts`
  - single source of truth for `en` and `sw`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useSpeech.ts`
  - microphone capture
  - transcript review state
  - speech playback state
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/hooks/useChat.ts`
  - voice transcript submission through the normal chat path
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/ChatInterface.tsx`
  - English voice input controls
  - Swahili audio playback controls
  - patient language selector

### Regression coverage

- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/e2e/swahili-refusal-smoke.spec.ts`
  - record refusal flow
  - latest-document refusal flow
- `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/ci.yml`
  - dedicated Swahili refusal CI artifact
- `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/medgemma-tone-nightly.yml`
  - dedicated Swahili refusal nightly artifact

---

## What still needs refactoring

1. **Rename `multilingual.py` to a narrower ownership name**
   - target name: `patient_language.py`
   - reason: the current file is no longer a general multilingual layer
2. **Deploy the extracted Swahili TTS runtime separately**
   - service boundary now exists
   - compose-backed worker/container deployment is now in place with `SPEECH_SYNTHESIS_BACKEND=http`
   - remaining work is release documentation and operational rollout hardening
3. **Add an explicit capability registry shared by backend and frontend**
   - `en`: text + ASR
   - `sw`: text + TTS
4. **Separate product-ready deterministic translation rules from fallback translation**
   - current behavior works, but the file is carrying too many responsibilities
5. **Add speech observability**
   - ASR latency
   - transcript edit rate
   - TTS latency
   - TTS cache hit rate

---

## Next steps

### Immediate

- Record the first real-human English MedASR benchmark clips and publish transcript-quality metrics.
- Enable actual backend training execution inside `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/swa_tts_trainer_adapter.py`.
- Promote `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh` into environment-specific deploy automation.

### After that

- Add a release-grade English voice smoke test.
- Split deterministic Swahili translation patterns into smaller modules by answer type.
- Add speech observability for ASR confidence, transcript edit rate, TTS latency, and cache hit rate.
