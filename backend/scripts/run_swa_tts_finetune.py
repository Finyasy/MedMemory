#!/usr/bin/env python3
"""Stage and optionally execute the Swahili TTS fine-tune job.

Examples:
    cd backend
    uv run python scripts/run_swa_tts_finetune.py \
      --config configs/speech/swa_tts_finetune_v1.json

    cd backend
    uv run python scripts/run_swa_tts_finetune.py \
      --config configs/speech/swa_tts_finetune_v1.json \
      --trainer-runtime mock \
      --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from scripts.prepare_swa_tts_finetune import load_config, prepare_job

ENV_KEYS = {
    "resolved_config": "MEDMEMORY_TTS_RESOLVED_CONFIG",
    "dataset_summary": "MEDMEMORY_TTS_DATASET_SUMMARY",
    "audio_base_dir": "MEDMEMORY_TTS_AUDIO_BASE_DIR",
    "train_metadata": "MEDMEMORY_TTS_TRAIN_METADATA",
    "validation_metadata": "MEDMEMORY_TTS_VALIDATION_METADATA",
    "test_metadata": "MEDMEMORY_TTS_TEST_METADATA",
    "checkpoint_dir": "MEDMEMORY_TTS_CHECKPOINT_DIR",
    "reports_dir": "MEDMEMORY_TTS_REPORTS_DIR",
    "base_model_path": "MEDMEMORY_TTS_BASE_MODEL_PATH",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/speech/swa_tts_finetune_v1.json"),
        help="JSON config describing the fine-tune job.",
    )
    parser.add_argument(
        "--resolved-config",
        type=Path,
        help="Use a pre-generated resolved config instead of preparing from the source config.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override the configured outputs.root_dir if needed.",
    )
    parser.add_argument(
        "--trainer-runtime",
        choices=("external_command", "mock"),
        help="Override the configured trainer runtime.",
    )
    parser.add_argument(
        "--trainer-command",
        type=str,
        help="Command or template to execute when using the external_command runtime.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the selected trainer runtime after staging the workspace.",
    )
    return parser.parse_args()


def _load_resolved_config(args: argparse.Namespace) -> dict[str, Any]:
    if args.resolved_config:
        return json.loads(args.resolved_config.expanduser().resolve().read_text(encoding="utf-8"))

    config, repo_root = load_config(args.config)
    resolved = prepare_job(config, repo_root, args.output_dir)
    output_root = Path(resolved["outputs"]["resolved_root_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_path = output_root / "resolved_config.json"
    dataset_summary_path = output_root / "dataset_summary.json"
    resolved_path.write_text(json.dumps(resolved, indent=2, ensure_ascii=False), encoding="utf-8")
    dataset_summary_path.write_text(
        json.dumps(resolved["dataset_summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return resolved


def _load_manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_metadata_csv(
    *,
    manifest_path: Path,
    output_path: Path,
    audio_base_dir: Path,
    audio_path_field: str,
    text_field: str,
    speaker_field: str,
) -> int:
    rows = _load_manifest_rows(manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["audio_file", "text", "speaker_id"],
            delimiter="|",
        )
        writer.writeheader()
        for row in rows:
            audio_rel = str(Path(row[audio_path_field]))
            audio_path = (audio_base_dir / audio_rel).resolve()
            writer.writerow(
                {
                    "audio_file": str(audio_path),
                    "text": str(row[text_field]),
                    "speaker_id": str(row.get(speaker_field, "speaker-0")),
                }
            )
    return len(rows)


def stage_trainer_workspace(
    resolved: dict[str, Any],
    *,
    trainer_runtime: str,
) -> dict[str, Any]:
    output_root = Path(resolved["outputs"]["resolved_root_dir"])
    trainer_cfg = resolved.get("trainer", {})
    workspace_dir = Path(
        trainer_cfg.get("resolved_workspace_dir", output_root / "trainer_workspace")
    )
    workspace_dir.mkdir(parents=True, exist_ok=True)

    dataset = resolved["dataset"]
    audio_base_dir = Path(dataset["resolved_audio_base_dir"])
    manifests = {
        split_name: Path(path)
        for split_name, path in dataset["resolved_manifests"].items()
    }

    metadata_paths = {
        "train": workspace_dir / "metadata_train.csv",
        "validation": workspace_dir / "metadata_validation.csv",
        "test": workspace_dir / "metadata_test.csv",
    }

    split_counts = {}
    for split_name, metadata_path in metadata_paths.items():
        split_counts[split_name] = _write_metadata_csv(
            manifest_path=manifests[split_name],
            output_path=metadata_path,
            audio_base_dir=audio_base_dir,
            audio_path_field=dataset.get("audio_path_field", "audio_path"),
            text_field=dataset.get("text_field", "text"),
            speaker_field=dataset.get("speaker_field", "speaker_id"),
        )

    resolved_config_path = output_root / "resolved_config.json"
    dataset_summary_path = output_root / "dataset_summary.json"
    resolved_config_path.write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    dataset_summary_path.write_text(
        json.dumps(resolved["dataset_summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    env_exports = {
        ENV_KEYS["resolved_config"]: str(resolved_config_path),
        ENV_KEYS["dataset_summary"]: str(dataset_summary_path),
        ENV_KEYS["audio_base_dir"]: str(audio_base_dir),
        ENV_KEYS["train_metadata"]: str(metadata_paths["train"]),
        ENV_KEYS["validation_metadata"]: str(metadata_paths["validation"]),
        ENV_KEYS["test_metadata"]: str(metadata_paths["test"]),
        ENV_KEYS["checkpoint_dir"]: str(resolved["outputs"]["resolved_checkpoint_dir"]),
        ENV_KEYS["reports_dir"]: str(resolved["outputs"]["resolved_reports_dir"]),
        ENV_KEYS["base_model_path"]: str(resolved["base_model"]["resolved_local_path"]),
    }
    command_values = {
        "resolved_config": str(resolved_config_path),
        "dataset_summary": str(dataset_summary_path),
        "audio_base_dir": str(audio_base_dir),
        "train_metadata": str(metadata_paths["train"]),
        "validation_metadata": str(metadata_paths["validation"]),
        "test_metadata": str(metadata_paths["test"]),
        "checkpoint_dir": str(resolved["outputs"]["resolved_checkpoint_dir"]),
        "reports_dir": str(resolved["outputs"]["resolved_reports_dir"]),
        "base_model_path": str(resolved["base_model"]["resolved_local_path"]),
        "workspace_dir": str(workspace_dir),
        "backend_root": str(output_root.parents[2]),
    }
    command_template = str(trainer_cfg.get("command_template", "")).strip()
    rendered_command = (
        _render_command(command_template, command_values) if command_template else None
    )

    launch_plan = {
        "job_name": resolved["job_name"],
        "trainer_runtime": trainer_runtime,
        "workspace_dir": str(workspace_dir),
        "split_counts": split_counts,
        "env_exports": env_exports,
        "command_template": command_template or None,
        "rendered_command": rendered_command,
        "dataset_sha": dataset.get("dataset_sha"),
        "base_model": resolved["base_model"]["model_id"],
        "base_model_path": resolved["base_model"]["resolved_local_path"],
    }
    launch_plan_path = workspace_dir / "launch_plan.json"
    launch_plan_path.write_text(
        json.dumps(launch_plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    launch_script_path = workspace_dir / "run_external_trainer.sh"
    launch_script_path.write_text(
        _build_launch_script(env_exports, rendered_command),
        encoding="utf-8",
    )
    launch_script_path.chmod(0o755)
    env_file_path = workspace_dir / "trainer.env"
    env_file_path.write_text(_build_env_file(env_exports), encoding="utf-8")

    return {
        "workspace_dir": workspace_dir,
        "launch_plan_path": launch_plan_path,
        "launch_script_path": launch_script_path,
        "env_file_path": env_file_path,
        "metadata_paths": metadata_paths,
        "env_exports": env_exports,
        "command_template": command_template or None,
        "rendered_command": rendered_command,
        "command_values": command_values,
        "split_counts": split_counts,
    }


def _build_env_file(env_exports: dict[str, str]) -> str:
    return "".join(f'{key}="{value}"\n' for key, value in env_exports.items())


def _build_launch_script(env_exports: dict[str, str], rendered_command: str | None) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
    ]
    for key, value in env_exports.items():
        lines.append(f'export {key}="{value}"')
    if rendered_command:
        lines.append(f'export MEDMEMORY_TTS_RENDERED_COMMAND="{rendered_command}"')
    lines.append(': "${SWA_TTS_TRAINER_CMD:=${MEDMEMORY_TTS_RENDERED_COMMAND:-}}"')
    lines.append(': "${SWA_TTS_TRAINER_CMD:?Set SWA_TTS_TRAINER_CMD or configure trainer.command_template.}"')
    lines.append('exec bash -lc "${SWA_TTS_TRAINER_CMD}"')
    return "\n".join(lines) + "\n"


def _render_command(command_template: str, command_values: dict[str, str]) -> str:
    try:
        return command_template.format(**command_values)
    except KeyError as exc:
        missing_key = exc.args[0]
        raise ValueError(
            f"trainer.command_template references unknown placeholder `{missing_key}`"
        ) from exc


def execute_job(
    *,
    trainer_runtime: str,
    trainer_command: str | None,
    staged: dict[str, Any],
) -> dict[str, Any]:
    workspace_dir = Path(staged["workspace_dir"])
    if trainer_runtime == "mock":
        result = {
            "status": "mock_executed",
            "trainer_runtime": trainer_runtime,
            "workspace_dir": str(workspace_dir),
            "env_exports": staged["env_exports"],
        }
        result_path = workspace_dir / "mock_execution.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"result_path": str(result_path), **result}

    if trainer_runtime != "external_command":
        raise ValueError(f"Unsupported trainer runtime: {trainer_runtime}")

    command = (
        trainer_command
        or staged.get("rendered_command")
        or os.environ.get("SWA_TTS_TRAINER_CMD")
    )
    if not command:
        raise ValueError(
            "No trainer command configured. Pass --trainer-command, set trainer.command_template, or set SWA_TTS_TRAINER_CMD."
        )

    env = os.environ.copy()
    env.update(staged["env_exports"])
    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=str(workspace_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result = {
        "status": "executed" if completed.returncode == 0 else "failed",
        "trainer_runtime": trainer_runtime,
        "trainer_command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    result_path = workspace_dir / "trainer_execution.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Trainer command failed with exit code {completed.returncode}. See {result_path}."
        )
    return {"result_path": str(result_path), **result}


def main() -> None:
    args = parse_args()
    resolved = _load_resolved_config(args)
    trainer_runtime = args.trainer_runtime or resolved.get("trainer", {}).get(
        "runtime",
        "external_command",
    )
    staged = stage_trainer_workspace(resolved, trainer_runtime=trainer_runtime)
    result: dict[str, Any] = {
        "job_name": resolved["job_name"],
        "trainer_runtime": trainer_runtime,
        "workspace_dir": str(staged["workspace_dir"]),
        "launch_plan": str(staged["launch_plan_path"]),
        "launch_script": str(staged["launch_script_path"]),
        "env_file": str(staged["env_file_path"]),
        "split_counts": staged["split_counts"],
    }
    if args.execute:
        execution = execute_job(
            trainer_runtime=trainer_runtime,
            trainer_command=args.trainer_command,
            staged=staged,
        )
        result["execution"] = execution
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
