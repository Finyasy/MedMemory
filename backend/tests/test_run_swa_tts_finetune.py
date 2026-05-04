from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.prepare_swa_tts_finetune import prepare_job
from scripts.run_swa_tts_finetune import execute_job, stage_trainer_workspace


def _write_manifest(path: Path, audio_path: str, split_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": f"{split_name}-1",
                "audio_path": audio_path,
                "text": "Habari yako",
                "speaker_id": "speaker-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _build_resolved_job(repo_root: Path, command_template: str | None = None) -> dict:
    model_dir = repo_root / "models" / "mms-tts-swh"
    model_dir.mkdir(parents=True)
    dataset_root = repo_root / "data" / "waxal_swa_tts"
    manifest_dir = dataset_root / "manifests"
    for split_name in ("train", "validation", "test"):
        audio_dir = dataset_root / "exported_audio" / split_name
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_file = audio_dir / f"{split_name}-sample.mp3"
        audio_file.write_bytes(b"ID3")
        _write_manifest(
            manifest_dir / f"{split_name}.manifest.jsonl",
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
            "dataset_id": "google/WaxalNLP",
            "dataset_sha": "demo-sha",
            "audio_base_dir": str(dataset_root.relative_to(repo_root)),
            "manifests": {
                "train": str((manifest_dir / "train.manifest.jsonl").relative_to(repo_root)),
                "validation": str((manifest_dir / "validation.manifest.jsonl").relative_to(repo_root)),
                "test": str((manifest_dir / "test.manifest.jsonl").relative_to(repo_root)),
            },
            "audio_path_field": "audio_path",
            "text_field": "text",
            "speaker_field": "speaker_id",
        },
        "training": {"learning_rate": 2e-5},
        "trainer": {
            "runtime": "external_command",
            "workspace_dir": "artifacts/tts_finetune/swa_tts_v1/trainer_workspace",
            **({"command_template": command_template} if command_template else {}),
        },
        "outputs": {
            "root_dir": "artifacts/tts_finetune/swa_tts_v1",
            "checkpoint_dir": "artifacts/tts_finetune/swa_tts_v1/checkpoints",
            "reports_dir": "artifacts/tts_finetune/swa_tts_v1/reports",
        },
    }
    return prepare_job(config, repo_root, None)


def test_stage_trainer_workspace_exports_metadata(tmp_path):
    resolved = _build_resolved_job(tmp_path)

    staged = stage_trainer_workspace(resolved, trainer_runtime="external_command")

    train_metadata = staged["metadata_paths"]["train"]
    assert train_metadata.exists()
    rows = train_metadata.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "audio_file|text|speaker_id"
    assert "Habari yako" in rows[1]
    assert staged["launch_plan_path"].exists()
    assert staged["launch_script_path"].exists()
    assert staged["env_file_path"].exists()


def test_execute_job_mock_writes_execution_result(tmp_path):
    resolved = _build_resolved_job(tmp_path)
    staged = stage_trainer_workspace(resolved, trainer_runtime="mock")

    result = execute_job(
        trainer_runtime="mock",
        trainer_command=None,
        staged=staged,
    )

    assert result["status"] == "mock_executed"
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert payload["trainer_runtime"] == "mock"
    assert payload["env_exports"]["MEDMEMORY_TTS_TRAIN_METADATA"].endswith(
        "metadata_train.csv"
    )


def test_execute_job_external_command_uses_rendered_template(tmp_path):
    trainer_adapter = (
        Path("/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts")
        / "swa_tts_trainer_adapter.py"
    )
    command_template = (
        f"{sys.executable} {trainer_adapter} "
        "--backend coqui_vits "
        "--resolved-config {resolved_config} "
        "--dataset-summary {dataset_summary} "
        "--audio-base-dir {audio_base_dir} "
        "--train-metadata {train_metadata} "
        "--validation-metadata {validation_metadata} "
        "--test-metadata {test_metadata} "
        "--checkpoint-dir {checkpoint_dir} "
        "--reports-dir {reports_dir} "
        "--base-model-path {base_model_path} "
        "--output-json {workspace_dir}/external_command_contract.json"
    )
    resolved = _build_resolved_job(tmp_path, command_template=command_template)
    staged = stage_trainer_workspace(resolved, trainer_runtime="external_command")

    result = execute_job(
        trainer_runtime="external_command",
        trainer_command=None,
        staged=staged,
    )

    assert result["status"] == "executed"
    contract_path = Path(staged["workspace_dir"]) / "external_command_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    assert payload["status"] == "prepared_backend"
    assert payload["backend"] == "coqui_vits"
