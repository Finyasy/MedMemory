#!/usr/bin/env python3
"""Run the full real-use-case baseline vs QLoRA experiment.

This script orchestrates:
1) Build a 50-200 example eval set from real conversation data.
2) Fine-tune MedGemma with QLoRA on the train split.
3) Compare baseline vs finetuned outputs on the eval split.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


def detect_device_kind() -> str:
    try:
        import torch
    except Exception:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", type=str, default="models/medgemma-1.5-4b-it")
    parser.add_argument("--num-examples", type=int, default=120)
    parser.add_argument(
        "--allow-small",
        action="store_true",
        help="Allow fewer than 50 examples when building dataset.",
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("artifacts/qlora_experiment")
    )
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--skip-train",
        action="store_true",
        help="Only build dataset and run baseline/final evaluation.",
    )
    return parser.parse_args()


def run_command(cmd: list[str]) -> None:
    rendered = " ".join(shlex.quote(part) for part in cmd)
    print(f"\n$ {rendered}")
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    device_kind = detect_device_kind()
    output_root = args.output_root
    dataset_dir = output_root / "dataset"
    train_dir = output_root / "training"
    eval_dir = output_root / "evaluation"

    train_compat_args: list[str] = []
    eval_compat_args: list[str] = []
    if device_kind != "cuda":
        # QLoRA 4-bit and bf16 paths are CUDA-only in this pipeline.
        train_compat_args.extend(["--no-use-4bit", "--no-bf16"])
        eval_compat_args.extend(["--no-use-4bit", "--no-bf16"])
        print(
            f"Detected {device_kind.upper()} backend. "
            "Using non-4bit, non-bf16 compatibility flags.",
        )

    run_command(
        [
            "python",
            "scripts/build_real_usecase_dataset.py",
            "--num-examples",
            str(args.num_examples),
            "--output-dir",
            str(dataset_dir),
            "--seed",
            str(args.seed),
            *(["--allow-small"] if args.allow_small else []),
        ]
    )

    adapter_dir = train_dir / "adapter"
    if not args.skip_train:
        run_command(
            [
                "python",
                "scripts/train_qlora_on_usecases.py",
                "--train-file",
                str(dataset_dir / "train.jsonl"),
                "--eval-file",
                str(dataset_dir / "eval.jsonl"),
                "--model-id",
                args.model_id,
                "--output-dir",
                str(train_dir),
                "--epochs",
                str(args.epochs),
                "--learning-rate",
                str(args.learning_rate),
                "--seed",
                str(args.seed),
                *train_compat_args,
            ]
        )

    evaluate_cmd = [
        "python",
        "scripts/evaluate_baseline_vs_qlora.py",
        "--eval-file",
        str(dataset_dir / "eval.jsonl"),
        "--model-id",
        args.model_id,
        "--output-dir",
        str(eval_dir),
        "--max-new-tokens",
        str(args.max_new_tokens),
        *eval_compat_args,
    ]
    if adapter_dir.exists():
        evaluate_cmd.extend(["--adapter-dir", str(adapter_dir)])
    run_command(evaluate_cmd)

    print("\nQLoRA experiment finished.")
    print(f"- Dataset: {dataset_dir}")
    print(f"- Training outputs: {train_dir}")
    print(f"- Evaluation report: {eval_dir / 'report.md'}")


if __name__ == "__main__":
    main()
