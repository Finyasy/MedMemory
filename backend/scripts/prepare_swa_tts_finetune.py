"""Validate and resolve the Swahili TTS fine-tune job configuration.

Usage:
    uv run python scripts/prepare_swa_tts_finetune.py \
      --config configs/speech/swa_tts_finetune_v1.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/speech/swa_tts_finetune_v1.json"),
        help="JSON config describing the fine-tune job.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override the configured outputs.root_dir if needed.",
    )
    return parser.parse_args()


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_config(config_path: Path) -> tuple[dict[str, Any], Path]:
    resolved_config_path = config_path.expanduser().resolve()
    payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    return payload, resolved_config_path.parents[2].resolve()


def _load_manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {manifest_path}:{line_number}"
                ) from exc
    return rows


def _summarize_split(
    *,
    rows: list[dict[str, Any]],
    manifest_path: Path,
    repo_root: Path,
    audio_base_dir: Path,
    audio_field: str,
    text_field: str,
    speaker_field: str,
) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"Manifest is empty: {manifest_path}")

    extensions = Counter()
    speakers = Counter()
    missing_audio: list[str] = []
    text_lengths: list[int] = []
    resolved_rows: list[dict[str, Any]] = []

    for row in rows:
        for required_key in ("id", audio_field, text_field):
            if required_key not in row or not row[required_key]:
                raise ValueError(
                    f"Manifest {manifest_path} missing required field `{required_key}` in row {row}"
                )
        audio_path = _resolve_path(audio_base_dir, str(row[audio_field]))
        if not audio_path.exists():
            missing_audio.append(str(audio_path))
        extensions[audio_path.suffix or "<none>"] += 1
        if row.get(speaker_field):
            speakers[str(row[speaker_field])] += 1
        text_lengths.append(len(str(row[text_field])))
        resolved_rows.append(
            {
                "id": row["id"],
                "audio_path": str(audio_path),
                "text": row[text_field],
            }
        )

    if missing_audio:
        raise FileNotFoundError(
            "Missing audio files:\n" + "\n".join(f"- {path}" for path in missing_audio[:20])
        )

    return {
        "manifest_path": str(manifest_path),
        "row_count": len(rows),
        "audio_extensions": dict(extensions),
        "speaker_count": len(speakers),
        "average_text_length": round(sum(text_lengths) / len(text_lengths), 2),
        "sample_rows": resolved_rows[:5],
        "relative_manifest_path": str(manifest_path.relative_to(repo_root)),
    }


def prepare_job(config: dict[str, Any], repo_root: Path, output_dir_override: Path | None) -> dict[str, Any]:
    dataset = config["dataset"]
    outputs = config["outputs"]
    trainer = config.get("trainer", {})
    output_root = (
        _resolve_path(repo_root, str(output_dir_override))
        if output_dir_override
        else _resolve_path(repo_root, outputs["root_dir"])
    )
    output_root.mkdir(parents=True, exist_ok=True)
    manifests = dataset["manifests"]
    audio_base_dir = _resolve_path(repo_root, dataset.get("audio_base_dir", "."))
    split_summaries: dict[str, Any] = {}
    for split_name, raw_manifest_path in manifests.items():
        manifest_path = _resolve_path(repo_root, raw_manifest_path)
        rows = _load_manifest_rows(manifest_path)
        split_summaries[split_name] = _summarize_split(
            rows=rows,
            manifest_path=manifest_path,
            repo_root=repo_root,
            audio_base_dir=audio_base_dir,
            audio_field=dataset.get("audio_path_field", "audio_path"),
            text_field=dataset.get("text_field", "text"),
            speaker_field=dataset.get("speaker_field", "speaker_id"),
        )

    resolved = {
        "job_name": config["job_name"],
        "base_model": {
          **config["base_model"],
          "resolved_local_path": str(_resolve_path(repo_root, config["base_model"]["local_path"])),
        },
        "dataset": {
            **dataset,
            "resolved_audio_base_dir": str(audio_base_dir),
            "resolved_manifests": {
                split_name: summary["manifest_path"]
                for split_name, summary in split_summaries.items()
            },
        },
        "training": config["training"],
        "trainer": {
            **trainer,
            "resolved_workspace_dir": str(
                _resolve_path(repo_root, trainer.get("workspace_dir", str(output_root / "trainer_workspace")))
            ),
        },
        "outputs": {
            **outputs,
            "resolved_root_dir": str(output_root),
            "resolved_checkpoint_dir": str(_resolve_path(repo_root, outputs["checkpoint_dir"])),
            "resolved_reports_dir": str(_resolve_path(repo_root, outputs["reports_dir"])),
        },
        "regression_set": config.get("regression_set", {}),
        "dataset_summary": split_summaries,
    }
    return resolved


def main() -> None:
    args = parse_args()
    config, repo_root = load_config(args.config)
    resolved = prepare_job(config, repo_root, args.output_dir)
    output_root = Path(resolved["outputs"]["resolved_root_dir"])
    (output_root / "resolved_config.json").write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_root / "dataset_summary.json").write_text(
        json.dumps(resolved["dataset_summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "job_name": resolved["job_name"],
            "output_dir": str(output_root),
            "splits": {
                split_name: summary["row_count"]
                for split_name, summary in resolved["dataset_summary"].items()
            },
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
