#!/usr/bin/env python3
"""Run provider sync dry-run checks across dashboard connections."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class DryRunResult:
    connection_id: int
    provider_slug: str
    ok: bool
    mode: str
    details: str
    counts: dict[str, int]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Call /dashboard/patient/{patient_id}/connections/{connection_id}/sync/dry-run "
            "for each matching connection."
        )
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000/api/v1",
        help="Backend API base URL (default: http://localhost:8000/api/v1)",
    )
    parser.add_argument(
        "--patient-id",
        type=int,
        required=True,
        help="Patient ID used for dashboard connections.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MEDMEMORY_JWT") or os.getenv("ACCESS_TOKEN"),
        help="JWT bearer token (or set MEDMEMORY_JWT / ACCESS_TOKEN env var).",
    )
    parser.add_argument(
        "--provider-slug",
        help="Optional provider slug filter.",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include inactive connections (default filters to active only).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout seconds (default: 30).",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON output.",
    )
    return parser.parse_args()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    verify: bool,
) -> Any:
    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        body = response.text.strip().replace("\n", " ")
        raise RuntimeError(f"HTTP {response.status_code} {url} -> {body[:400]}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Non-JSON response from {url}") from exc


def _load_connections(
    *,
    base_url: str,
    patient_id: int,
    headers: dict[str, str],
    timeout: int,
    verify: bool,
) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/dashboard/patient/{patient_id}/connections"
    payload = _request_json(
        "GET",
        url,
        headers=headers,
        timeout=timeout,
        verify=verify,
    )
    if not isinstance(payload, list):
        raise RuntimeError("Connections endpoint returned non-list response")
    return [row for row in payload if isinstance(row, dict)]


def _dry_run_connection(
    *,
    base_url: str,
    patient_id: int,
    connection: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
    verify: bool,
) -> DryRunResult:
    connection_id = int(connection["id"])
    provider_slug = str(connection.get("provider_slug") or "unknown")
    url = (
        f"{base_url.rstrip('/')}/dashboard/patient/{patient_id}/connections/"
        f"{connection_id}/sync/dry-run"
    )
    payload = _request_json(
        "POST",
        url,
        headers=headers,
        timeout=timeout,
        verify=verify,
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"Dry-run endpoint for connection {connection_id} returned non-object")
    return DryRunResult(
        connection_id=connection_id,
        provider_slug=provider_slug,
        ok=bool(payload.get("ok")),
        mode=str(payload.get("mode") or ""),
        details=str(payload.get("details") or ""),
        counts=payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
    )


def main() -> int:
    args = _parse_args()
    if not args.token:
        print("Missing token. Pass --token or set MEDMEMORY_JWT.", file=sys.stderr)
        return 2

    headers = _auth_headers(args.token)
    verify = not args.insecure

    try:
        connections = _load_connections(
            base_url=args.base_url,
            patient_id=args.patient_id,
            headers=headers,
            timeout=args.timeout,
            verify=verify,
        )
    except Exception as exc:
        print(f"Failed to load connections: {exc}", file=sys.stderr)
        return 2

    selected: list[dict[str, Any]] = []
    for row in connections:
        if args.provider_slug and row.get("provider_slug") != args.provider_slug:
            continue
        if not args.include_inactive and not bool(row.get("is_active", True)):
            continue
        selected.append(row)

    if not selected:
        print("No matching connections found.")
        return 0

    results: list[DryRunResult] = []
    has_failure = False
    for row in selected:
        try:
            result = _dry_run_connection(
                base_url=args.base_url,
                patient_id=args.patient_id,
                connection=row,
                headers=headers,
                timeout=args.timeout,
                verify=verify,
            )
            results.append(result)
            has_failure = has_failure or (not result.ok)
        except Exception as exc:
            has_failure = True
            results.append(
                DryRunResult(
                    connection_id=int(row["id"]),
                    provider_slug=str(row.get("provider_slug") or "unknown"),
                    ok=False,
                    mode="error",
                    details=str(exc),
                    counts={},
                )
            )

    if args.json:
        output = [
            {
                "connection_id": result.connection_id,
                "provider_slug": result.provider_slug,
                "ok": result.ok,
                "mode": result.mode,
                "counts": result.counts,
                "details": result.details,
            }
            for result in results
        ]
        print(json.dumps(output, indent=2))
    else:
        for result in results:
            status = "PASS" if result.ok else "FAIL"
            counts_text = (
                ", ".join(f"{key}={value}" for key, value in sorted(result.counts.items()))
                if result.counts
                else "-"
            )
            print(
                f"[{status}] conn={result.connection_id} provider={result.provider_slug} "
                f"mode={result.mode} counts={counts_text}"
            )
            if result.details:
                print(f"  details: {result.details}")

    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
