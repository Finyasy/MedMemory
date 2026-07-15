# Human English MedASR Evaluation Set (`human_en_v1`)

This directory is the tracked scaffold for the **real-human** MedASR evaluation set.

## Goal

Measure MedASR quality on **actual human speech** from the MedMemory product context:

- patient questions spoken in English
- clinician record-review questions spoken in English
- quiet and mildly noisy capture conditions
- laptop and phone microphones

## What is tracked here

- `prompts.json` — prompt pack to record
- `manifest.template.jsonl` — schema example for recordings

## What is not committed

- raw audio recordings under `audio/`

Those files are intentionally ignored in git because they may contain sensitive
voice data.

## Required manifest fields

- `id`
- `audio_path`
- `reference`

## Strongly recommended metadata

- `role`: `patient` or `clinician`
- `speaker_id`
- `speaker_gender`
- `accent_region`
- `capture_device`
- `environment`
- `notes`

## Collection protocol

1. Recruit at least **4 speakers**:
   - 2 patient-style speakers
   - 2 clinician-style speakers
2. Record every prompt in:
   - one quiet setting
   - one mildly noisy setting
3. Save recordings under `audio/`.
4. Copy `manifest.template.jsonl` to `manifest.jsonl` and replace the placeholder
   rows with real recordings.
5. Validate the manifest:

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory/backend
uv run python scripts/validate_speech_eval_manifest.py \
  --manifest data/speech_eval/human_en_v1/manifest.jsonl
```

6. Run the MedASR evaluation:

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory/backend
uv run python scripts/evaluate_speech_transcription.py \
  --manifest data/speech_eval/human_en_v1/manifest.jsonl \
  --output-dir artifacts/speech_eval/human_en_v1 \
  --compare-plain-ctc
```

## Acceptance targets

- baseline WER reported overall and by role
- baseline confidence reported overall and by environment
- transcript edit-rate tracked manually in a follow-up report
