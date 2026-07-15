from __future__ import annotations

import json
from pathlib import Path

from scripts.prepare_swa_tts_finetune import prepare_job


def _write_manifest(path: Path, audio_path: str, split_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": f"{split_name}-1",
                        "audio_path": audio_path,
                        "text": "Habari yako",
                        "speaker_id": "speaker-1",
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_prepare_job_resolves_manifests_and_outputs(tmp_path):
    repo_root = tmp_path
    model_dir = repo_root / "models" / "mms-tts-swh"
    model_dir.mkdir(parents=True)
    dataset_root = repo_root / "data" / "waxal_swa_tts"
    manifest_dir = dataset_root / "manifests"
    audio_dir = dataset_root / "exported_audio" / "train"
    audio_file = audio_dir / "sample.mp3"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"ID3")

    train_manifest = manifest_dir / "train.manifest.jsonl"
    validation_manifest = manifest_dir / "validation.manifest.jsonl"
    test_manifest = manifest_dir / "test.manifest.jsonl"
    for split_name, manifest_path in (
        ("train", train_manifest),
        ("validation", validation_manifest),
        ("test", test_manifest),
    ):
        _write_manifest(
            manifest_path,
            str(audio_file.relative_to(dataset_root)),
            split_name,
        )

    config = {
        "job_name": "swa_tts_v1",
        "base_model": {
            "model_id": "facebook/mms-tts-swh",
            "local_path": "models/mms-tts-swh",
        },
        "dataset": {
            "audio_base_dir": str(dataset_root.relative_to(repo_root)),
            "manifests": {
                "train": str(train_manifest.relative_to(repo_root)),
                "validation": str(validation_manifest.relative_to(repo_root)),
                "test": str(test_manifest.relative_to(repo_root)),
            },
            "audio_path_field": "audio_path",
            "text_field": "text",
            "speaker_field": "speaker_id",
        },
        "training": {"learning_rate": 2e-5},
        "outputs": {
            "root_dir": "artifacts/tts_finetune/swa_tts_v1",
            "checkpoint_dir": "artifacts/tts_finetune/swa_tts_v1/checkpoints",
            "reports_dir": "artifacts/tts_finetune/swa_tts_v1/reports",
        },
    }

    resolved = prepare_job(config, repo_root, None)

    assert resolved["base_model"]["resolved_local_path"] == str(model_dir.resolve())
    assert resolved["dataset"]["resolved_audio_base_dir"] == str(dataset_root.resolve())
    assert resolved["dataset_summary"]["train"]["row_count"] == 1
    assert resolved["dataset_summary"]["train"]["audio_extensions"] == {".mp3": 1}
    assert resolved["outputs"]["resolved_root_dir"].endswith("artifacts/tts_finetune/swa_tts_v1")
