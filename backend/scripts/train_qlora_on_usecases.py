#!/usr/bin/env python3
"""Fine-tune MedGemma on local real-use-case text data with QLoRA.

Example:
    cd backend
    uv run python scripts/train_qlora_on_usecases.py \
      --train-file data/qlora_usecases/train.jsonl \
      --eval-file data/qlora_usecases/eval.jsonl \
      --model-id models/medgemma-1.5-4b-it \
      --output-dir artifacts/qlora_usecase_run
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
from pathlib import Path
from typing import Any

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForImageTextToText,
    AutoProcessor,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-file", type=Path, required=True)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument(
        "--model-id",
        type=str,
        default="google/medgemma-1.5-4b-it",
        help="HF model id or local model path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/qlora_usecase_run"),
    )
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--train-batch-size", type=int, default=1)
    parser.add_argument("--eval-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--eval-steps", type=int, default=50)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--target-modules", type=str, default="all-linear")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-4bit", action="store_true", default=True)
    parser.add_argument("--no-use-4bit", action="store_false", dest="use_4bit")
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument("--no-bf16", action="store_false", dest="bf16")
    return parser.parse_args()


class CausalCollator:
    """Pad variable-length sequences and create labels for causal LM."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        batch = self.tokenizer.pad(features, return_tensors="pt")
        labels = batch["input_ids"].clone()
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            pad_id = self.tokenizer.eos_token_id
        labels[labels == pad_id] = -100
        batch["labels"] = labels
        return batch


def render_chat_text(tokenizer, messages: Any) -> str:
    """Render message list into training text."""
    if isinstance(messages, str):
        messages = json.loads(messages)
    if not isinstance(messages, list):
        raise ValueError("Each example must provide `messages` as a list.")

    if hasattr(tokenizer, "apply_chat_template") and getattr(
        tokenizer,
        "chat_template",
        None,
    ):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )

    lines: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        lines.append(f"{role.title()}: {content}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)
    tokenizer = processor.tokenizer if hasattr(processor, "tokenizer") else processor
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    raw_dataset = load_dataset(
        "json",
        data_files={
            "train": str(args.train_file),
            "validation": str(args.eval_file),
        },
    )

    def format_example(example: dict[str, Any]) -> dict[str, Any]:
        return {"text": render_chat_text(tokenizer, example["messages"])}

    formatted = raw_dataset.map(
        format_example,
        desc="Formatting examples",
    )

    def tokenize_example(example: dict[str, Any]) -> dict[str, Any]:
        return tokenizer(
            example["text"],
            truncation=True,
            max_length=args.max_seq_length,
        )

    tokenized = formatted.map(
        tokenize_example,
        remove_columns=formatted["train"].column_names,
        desc="Tokenizing",
    )

    if torch.cuda.is_available():
        device_kind = "cuda"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device_kind = "mps"
    else:
        device_kind = "cpu"

    if args.use_4bit and device_kind != "cuda":
        print(
            f"Disabling 4-bit quantization on {device_kind.upper()} (requires CUDA).",
        )
        args.use_4bit = False

    model_kwargs: dict[str, Any] = {
        "trust_remote_code": True,
    }
    if device_kind == "cuda":
        model_kwargs["device_map"] = "auto"
        model_kwargs["attn_implementation"] = "eager"
        model_kwargs["torch_dtype"] = torch.bfloat16 if args.bf16 else torch.float16
    elif device_kind == "mps":
        # Avoid auto-offload/meta tensors on MPS, which breaks backward passes.
        model_kwargs["device_map"] = None
        model_kwargs["low_cpu_mem_usage"] = False
        model_kwargs["attn_implementation"] = "eager"
        # Float16 training on MPS is prone to NaN loss/gradients for this model.
        model_kwargs["torch_dtype"] = torch.float32
    else:
        model_kwargs["device_map"] = "cpu"
        model_kwargs["torch_dtype"] = torch.float32

    if args.use_4bit:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=model_kwargs["torch_dtype"],
            bnb_4bit_quant_storage=model_kwargs["torch_dtype"],
        )

    model = AutoModelForImageTextToText.from_pretrained(args.model_id, **model_kwargs)
    if device_kind == "mps":
        model = model.to("mps")
    if args.use_4bit:
        model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=args.target_modules,
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    use_gradient_checkpointing = device_kind == "cuda"

    training_kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "num_train_epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "per_device_train_batch_size": args.train_batch_size,
        "per_device_eval_batch_size": args.eval_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "logging_steps": args.logging_steps,
        "eval_steps": args.eval_steps,
        "save_strategy": "epoch",
        "remove_unused_columns": False,
        "gradient_checkpointing": use_gradient_checkpointing,
        "bf16": args.bf16 and device_kind == "cuda",
        "fp16": (not args.bf16) and device_kind == "cuda",
        "optim": "paged_adamw_8bit" if args.use_4bit else "adamw_torch",
        "report_to": "none",
        "seed": args.seed,
    }
    if use_gradient_checkpointing:
        training_kwargs["gradient_checkpointing_kwargs"] = {"use_reentrant": False}
    ta_params = inspect.signature(TrainingArguments.__init__).parameters
    if "evaluation_strategy" in ta_params:
        training_kwargs["evaluation_strategy"] = "steps"
    else:
        training_kwargs["eval_strategy"] = "steps"
    training_args = TrainingArguments(**training_kwargs)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=CausalCollator(tokenizer),
    )
    train_result = trainer.train()
    eval_metrics = trainer.evaluate()

    metric_values: list[float] = []
    for metrics in (train_result.metrics, eval_metrics):
        for value in metrics.values():
            if isinstance(value, (int, float)):
                metric_values.append(float(value))
    if any(not math.isfinite(value) for value in metric_values):
        raise RuntimeError(
            "Training produced non-finite metrics. "
            "Try lower learning rate and/or smaller max sequence length.",
        )

    adapter_dir = output_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    processor.save_pretrained(adapter_dir)

    metrics_payload = {
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_metrics,
        "run_config": {
            "model_id": args.model_id,
            "train_file": str(args.train_file),
            "eval_file": str(args.eval_file),
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "train_batch_size": args.train_batch_size,
            "eval_batch_size": args.eval_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "max_seq_length": args.max_seq_length,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "target_modules": args.target_modules,
            "use_4bit": args.use_4bit,
            "bf16": args.bf16,
            "seed": args.seed,
        },
    }
    (output_dir / "train_metrics.json").write_text(
        json.dumps(metrics_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print("QLoRA training complete.")
    print(json.dumps(metrics_payload, indent=2))


if __name__ == "__main__":
    main()
