#!/usr/bin/env python3
"""Apply live provider sync configuration into a backend .env file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_json_input(raw: str) -> dict[str, str]:
    candidate = Path(raw)
    if candidate.exists():
        content = candidate.read_text(encoding="utf-8").strip()
        payload = json.loads(content)
    else:
        payload = json.loads(raw)

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object map")

    parsed: dict[str, str] = {}
    for key, value in payload.items():
        norm_key = str(key or "").strip()
        if not norm_key:
            continue
        if value is None:
            continue
        norm_value = str(value).strip()
        if not norm_value:
            continue
        parsed[norm_key] = norm_value
    return parsed


def _upsert_env(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    updated = False
    result: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            result.append(f"{prefix}{value}")
            updated = True
        else:
            result.append(line)
    if not updated:
        if result and result[-1].strip():
            result.append("")
        result.append(f"{prefix}{value}")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply provider sync env maps into a .env file. "
            "JSON inputs can be inline JSON strings or file paths."
        )
    )
    parser.add_argument(
        "--env-file",
        default="backend/.env",
        help="Path to .env file (default: backend/.env)",
    )
    parser.add_argument(
        "--base-urls",
        required=True,
        help="JSON object or file path for PROVIDER_SYNC_LIVE_BASE_URLS.",
    )
    parser.add_argument(
        "--bearer-tokens",
        help="JSON object or file path for PROVIDER_SYNC_LIVE_BEARER_TOKENS.",
    )
    parser.add_argument(
        "--api-keys",
        help="JSON object or file path for PROVIDER_SYNC_LIVE_API_KEYS.",
    )
    parser.add_argument(
        "--patient-identifier-system",
        default="",
        help="Optional PROVIDER_SYNC_LIVE_PATIENT_IDENTIFIER_SYSTEM value.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="PROVIDER_SYNC_LIVE_TIMEOUT_SECONDS (default: 30).",
    )
    parser.add_argument(
        "--verify-ssl",
        choices=["true", "false"],
        default="true",
        help="PROVIDER_SYNC_LIVE_VERIFY_SSL (default: true).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="PROVIDER_SYNC_LIVE_PAGE_SIZE (default: 200).",
    )
    parser.add_argument(
        "--max-pages-per-resource",
        type=int,
        default=20,
        help="PROVIDER_SYNC_LIVE_MAX_PAGES_PER_RESOURCE (default: 20).",
    )
    parser.add_argument(
        "--fallback-to-local-scan",
        choices=["true", "false"],
        default="true",
        help="PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN (default: true).",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print resulting env content instead of writing file.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    env_path = Path(args.env_file)
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    base_urls = _parse_json_input(args.base_urls)
    bearer_tokens = _parse_json_input(args.bearer_tokens) if args.bearer_tokens else {}
    api_keys = _parse_json_input(args.api_keys) if args.api_keys else {}

    lines = _upsert_env(lines, "PROVIDER_SYNC_LIVE_ENABLED", "true")
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN",
        args.fallback_to_local_scan,
    )
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_TIMEOUT_SECONDS",
        str(args.timeout_seconds),
    )
    lines = _upsert_env(lines, "PROVIDER_SYNC_LIVE_VERIFY_SSL", args.verify_ssl)
    lines = _upsert_env(lines, "PROVIDER_SYNC_LIVE_PAGE_SIZE", str(args.page_size))
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_MAX_PAGES_PER_RESOURCE",
        str(args.max_pages_per_resource),
    )
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_PATIENT_IDENTIFIER_SYSTEM",
        args.patient_identifier_system.strip(),
    )
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_BASE_URLS",
        json.dumps(base_urls, separators=(",", ":")),
    )
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_BEARER_TOKENS",
        json.dumps(bearer_tokens, separators=(",", ":")),
    )
    lines = _upsert_env(
        lines,
        "PROVIDER_SYNC_LIVE_API_KEYS",
        json.dumps(api_keys, separators=(",", ":")),
    )

    output = "\n".join(lines) + "\n"
    if args.print_only:
        print(output)
        return 0

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(output, encoding="utf-8")
    print(f"Updated {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
