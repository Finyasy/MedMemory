# WAXAL Swahili TTS Materialization

This directory holds the locally materialized `google/WaxalNLP` `swa_tts` subset
used for the Swahili TTS fine-tune pipeline.

## Layout

- `hf_cache/` — local Hugging Face dataset cache (ignored in git)
- `manifests/` — normalized JSONL manifests per split
- `exported_audio/` — only used if a dataset row exposes bytes instead of a file path
- `materialization_summary.json` — dataset/config metadata and split counts

## Materialize locally

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory/backend
uv run --group finetune python scripts/materialize_waxal_swa_tts.py \
  --output-dir data/waxal_swa_tts
```

## Output contract

Each manifest row contains:

- `id`
- `split`
- `audio_path`
- `text`
- `language`
- `source_dataset`
- `source_config`

Optional fields such as `speaker_id`, `gender`, `locale`, `region`, and
`duration` are preserved if the source subset exposes them.

## Fine-tune expectation

The next training step should read the normalized manifests from `manifests/`
instead of binding directly to the Hugging Face dataset loader. That keeps the
training pipeline reproducible and decouples it from online dataset access.

## Current local materialization

The current materialization was generated from:

- dataset: `google/WaxalNLP`
- logical subset: `swa_tts`
- repo subdir: `data/TTS/swa`
- dataset SHA: `beab143ae6d8a5e054281241afd76565ecb57e03`

Current split counts:

- `train`: `1387`
- `validation`: `192`
- `test`: `199`
