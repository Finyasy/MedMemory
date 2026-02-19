#!/usr/bin/env python3
"""Run a real MedGemma inference smoke check (non-mock, local runtime)."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from app.services.llm.model import LLMService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        type=str,
        default=(
            "You are running a MedMemory runtime smoke test. "
            "Reply with one short sentence confirming the runtime is responding."
        ),
        help="Prompt for the real inference check.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="Maximum new tokens for the smoke generation.",
    )
    parser.add_argument(
        "--expect-substring",
        type=str,
        default=None,
        help="Optional case-insensitive substring expected in model output.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional report output path.",
    )
    return parser.parse_args()


async def run_smoke(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    llm = LLMService.get_instance()
    start = time.time()
    response = await llm.generate(
        prompt=args.prompt,
        max_new_tokens=args.max_new_tokens,
        do_sample=False,
        temperature=0.0,
        top_p=1.0,
    )
    elapsed_ms = (time.time() - start) * 1000
    info = llm.get_model_info()

    output_text = (response.text or "").strip()
    passed = bool(output_text)
    failure_reason = None

    if not passed:
        failure_reason = "empty_output"
    elif (
        args.expect_substring
        and args.expect_substring.lower() not in output_text.lower()
    ):
        passed = False
        failure_reason = "missing_expected_substring"

    report: dict[str, Any] = {
        "passed": passed,
        "failure_reason": failure_reason,
        "runtime": info.get("runtime"),
        "device": info.get("device"),
        "model_name": info.get("model_name"),
        "max_new_tokens": args.max_new_tokens,
        "prompt_chars": len(args.prompt),
        "response_chars": len(output_text),
        "tokens_input": response.tokens_input,
        "tokens_generated": response.tokens_generated,
        "generation_time_ms": response.generation_time_ms,
        "elapsed_time_ms": elapsed_ms,
        "response_preview": output_text[:240],
    }
    return (0 if passed else 1), report


def main() -> int:
    args = parse_args()
    exit_code, report = asyncio.run(run_smoke(args))

    print("Real MedGemma Smoke Report")
    print("--------------------------")
    for key in [
        "passed",
        "failure_reason",
        "runtime",
        "device",
        "model_name",
        "tokens_input",
        "tokens_generated",
        "generation_time_ms",
        "elapsed_time_ms",
        "response_preview",
    ]:
        print(f"- {key}: {report.get(key)}")

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote report: {args.output_json}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
