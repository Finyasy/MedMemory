#!/usr/bin/env python3
"""Evaluate baseline MedGemma vs QLoRA adapter on local use-case eval data.

Example:
    cd backend
    uv run python scripts/evaluate_baseline_vs_qlora.py \
      --eval-file data/qlora_usecases/eval.jsonl \
      --model-id models/medgemma-1.5-4b-it \
      --adapter-dir artifacts/qlora_usecase_run/adapter \
      --output-dir artifacts/qlora_usecase_run/eval_compare
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.qlora_eval_utils import AggregateMetrics, compute_generation_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument(
        "--model-id",
        type=str,
        default="google/medgemma-1.5-4b-it",
        help="HF model id or local model path.",
    )
    parser.add_argument(
        "--adapter-dir",
        type=Path,
        default=None,
        help="Directory containing LoRA adapter weights.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/qlora_eval_compare"),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--use-4bit", action="store_true", default=True)
    parser.add_argument("--no-use-4bit", action="store_false", dest="use_4bit")
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument("--no-bf16", action="store_false", dest="bf16")
    return parser.parse_args()


def load_eval_examples(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise RuntimeError(f"No eval examples found in {path}")
    return rows


def _get_prompt(example: dict[str, Any]) -> str:
    prompt = example.get("prompt")
    if prompt:
        return prompt
    messages = example.get("messages", [])
    for message in messages:
        if message.get("role") == "user":
            return str(message.get("content", ""))
    raise ValueError("Unable to locate prompt in eval example.")


def _get_reference(example: dict[str, Any]) -> str:
    reference = example.get("reference_answer")
    if reference:
        return reference
    messages = example.get("messages", [])
    for message in messages:
        if message.get("role") == "assistant":
            return str(message.get("content", ""))
    raise ValueError("Unable to locate reference answer in eval example.")


def build_model_kwargs(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    kwargs: dict[str, Any] = {"trust_remote_code": True}
    if torch.cuda.is_available():
        device_kind = "cuda"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device_kind = "mps"
    else:
        device_kind = "cpu"

    if device_kind in {"cuda", "mps"}:
        kwargs["device_map"] = "auto"
        kwargs["attn_implementation"] = "eager"
        if device_kind == "cuda":
            kwargs["torch_dtype"] = torch.bfloat16 if args.bf16 else torch.float16
        else:
            kwargs["torch_dtype"] = torch.float32
    else:
        kwargs["device_map"] = "cpu"
        kwargs["torch_dtype"] = torch.float32
    if args.use_4bit:
        if device_kind != "cuda":
            print(
                f"Disabling 4-bit evaluation on {device_kind.upper()} (requires CUDA).",
            )
            args.use_4bit = False
        else:
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=kwargs["torch_dtype"],
                bnb_4bit_quant_storage=kwargs["torch_dtype"],
            )
    return kwargs, device_kind


def load_model_and_processor(
    model_id: str,
    args: argparse.Namespace,
    adapter_dir: Path | None = None,
):
    kwargs, device_kind = build_model_kwargs(args)
    if adapter_dir is not None and device_kind != "cuda":
        # PEFT adapter loading can break with auto offload/meta tensors on non-CUDA.
        kwargs["device_map"] = None
        kwargs["low_cpu_mem_usage"] = False
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    tokenizer = processor.tokenizer if hasattr(processor, "tokenizer") else processor
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForImageTextToText.from_pretrained(model_id, **kwargs)
    if adapter_dir is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter_dir))
    if kwargs.get("device_map") is None:
        if device_kind == "mps":
            model = model.to("mps")
        elif device_kind == "cpu":
            model = model.to("cpu")
    model.eval()
    return model, processor


def render_generation_prompt(tokenizer, prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template") and getattr(
        tokenizer,
        "chat_template",
        None,
    ):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    return f"User: {prompt}\nAssistant:"


def predict_texts(
    model,
    processor,
    prompts: list[str],
    *,
    max_new_tokens: int,
) -> list[str]:
    tokenizer = processor.tokenizer if hasattr(processor, "tokenizer") else processor
    predictions: list[str] = []
    model_device = next(model.parameters()).device

    for idx, prompt in enumerate(prompts, start=1):
        full_prompt = render_generation_prompt(tokenizer, prompt)
        inputs = processor(text=full_prompt, return_tensors="pt")
        inputs = {
            key: value.to(model_device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        generated_ids = outputs[0][inputs["input_ids"].shape[-1] :]
        text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        predictions.append(text)
        if idx % 10 == 0:
            print(f"Generated {idx}/{len(prompts)}")
    return predictions


def metrics_to_dict(metrics: AggregateMetrics) -> dict[str, float | int]:
    return {
        "exact_match": metrics.exact_match,
        "contains_reference": metrics.contains_reference,
        "token_f1": metrics.token_f1,
        "fact_precision": metrics.fact_precision,
        "fact_recall": metrics.fact_recall,
        "hallucination_rate": metrics.hallucination_rate,
        "n_examples": metrics.n_examples,
    }


def summarize_metrics(
    baseline: AggregateMetrics,
    finetuned: AggregateMetrics | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "baseline": metrics_to_dict(baseline),
    }
    if finetuned is None:
        return payload

    payload["finetuned"] = metrics_to_dict(finetuned)
    payload["delta"] = {
        "exact_match": finetuned.exact_match - baseline.exact_match,
        "contains_reference": finetuned.contains_reference
        - baseline.contains_reference,
        "token_f1": finetuned.token_f1 - baseline.token_f1,
        "fact_precision": finetuned.fact_precision - baseline.fact_precision,
        "fact_recall": finetuned.fact_recall - baseline.fact_recall,
        "hallucination_rate": finetuned.hallucination_rate
        - baseline.hallucination_rate,
    }
    return payload


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Baseline vs QLoRA Evaluation",
        "",
        f"- `created_at`: {summary['created_at']}",
        f"- `eval_file`: {summary['eval_file']}",
        f"- `model_id`: {summary['model_id']}",
        f"- `n_examples`: {summary['n_examples']}",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Finetuned | Delta |",
        "|---|---:|---:|---:|",
    ]

    baseline = summary["metrics"]["baseline"]
    finetuned = summary["metrics"].get("finetuned", {})
    delta = summary["metrics"].get("delta", {})
    metric_keys = [
        "exact_match",
        "contains_reference",
        "token_f1",
        "fact_precision",
        "fact_recall",
        "hallucination_rate",
    ]
    for key in metric_keys:
        base = baseline.get(key, 0.0)
        tuned = finetuned.get(key, 0.0) if finetuned else 0.0
        dlt = delta.get(key, 0.0) if delta else 0.0
        lines.append(f"| {key} | {base:.4f} | {tuned:.4f} | {dlt:+.4f} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    examples = load_eval_examples(args.eval_file, args.limit)
    prompts = [_get_prompt(example) for example in examples]
    references = [_get_reference(example) for example in examples]

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Running baseline generation...")
    baseline_model, baseline_processor = load_model_and_processor(args.model_id, args)
    baseline_predictions = predict_texts(
        baseline_model,
        baseline_processor,
        prompts,
        max_new_tokens=args.max_new_tokens,
    )
    baseline_metrics = compute_generation_metrics(baseline_predictions, references)

    finetuned_predictions: list[str] | None = None
    finetuned_metrics: AggregateMetrics | None = None
    if args.adapter_dir is not None:
        print("Running finetuned generation...")
        tuned_model, tuned_processor = load_model_and_processor(
            args.model_id,
            args,
            adapter_dir=args.adapter_dir,
        )
        finetuned_predictions = predict_texts(
            tuned_model,
            tuned_processor,
            prompts,
            max_new_tokens=args.max_new_tokens,
        )
        finetuned_metrics = compute_generation_metrics(
            finetuned_predictions, references
        )

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "eval_file": str(args.eval_file),
        "model_id": args.model_id,
        "adapter_dir": str(args.adapter_dir) if args.adapter_dir is not None else None,
        "n_examples": len(examples),
        "metrics": summarize_metrics(baseline_metrics, finetuned_metrics),
    }

    comparisons: list[dict[str, Any]] = []
    for idx, example in enumerate(examples):
        row = {
            "id": example.get("id", f"example-{idx}"),
            "prompt": prompts[idx],
            "reference_answer": references[idx],
            "baseline_prediction": baseline_predictions[idx],
        }
        if finetuned_predictions is not None:
            row["finetuned_prediction"] = finetuned_predictions[idx]
        comparisons.append(row)

    (output_dir / "metrics_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    with (output_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in comparisons:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")
    write_markdown_report(output_dir / "report.md", summary)

    print("Evaluation complete.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
