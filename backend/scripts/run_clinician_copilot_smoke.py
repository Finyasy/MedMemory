#!/usr/bin/env python3
"""Run a live clinician copilot smoke test against a local MedMemory backend.

Usage:
    cd backend
    python scripts/run_clinician_copilot_smoke.py --template chart_review
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("MEDMEMORY_BASE_URL", "http://localhost:8000"),
        help="Backend base URL.",
    )
    parser.add_argument(
        "--patient-email",
        default=os.getenv("E2E_EMAIL", "demo@medmemory.ai"),
        help="Patient login email.",
    )
    parser.add_argument(
        "--patient-password",
        default=os.getenv("E2E_PASSWORD", "demo-password"),
        help="Patient login password.",
    )
    parser.add_argument(
        "--clinician-email",
        default=os.getenv("E2E_CLINICIAN_EMAIL", "qa.clinician+20260218@example.com"),
        help="Clinician login email.",
    )
    parser.add_argument(
        "--clinician-password",
        default=os.getenv("E2E_CLINICIAN_PASSWORD", "DemoPass123!"),
        help="Clinician login password.",
    )
    parser.add_argument(
        "--clinician-name",
        default=os.getenv("E2E_CLINICIAN_NAME", "Dr QA Clinician"),
        help="Clinician full name used for signup if needed.",
    )
    parser.add_argument(
        "--clinician-registration",
        default=os.getenv("E2E_CLINICIAN_REG", "REG-2026-001"),
        help="Clinician registration number used for signup if needed.",
    )
    parser.add_argument(
        "--patient-id",
        type=int,
        help="Optional explicit patient id. Defaults to the first patient returned by the patient account.",
    )
    parser.add_argument(
        "--template",
        choices=("chart_review", "trend_review", "med_reconciliation", "data_quality"),
        default="chart_review",
        help="Clinician copilot template to run.",
    )
    parser.add_argument(
        "--prompt",
        default="Review this chart and surface the most important evidence for a clinician handoff.",
        help="Prompt passed to the clinician copilot run.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout for each request.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for the smoke summary JSON.",
    )
    return parser.parse_args()


def _raise_for_status(response: requests.Response, *, step: str, allowed_statuses: set[int] | None = None) -> None:
    if allowed_statuses and response.status_code in allowed_statuses:
        return
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text.strip()
        raise RuntimeError(
            f"{step} failed with HTTP {response.status_code}: {body or response.reason}"
        ) from exc


def call_json(
    session: requests.Session,
    *,
    method: str,
    url: str,
    step: str,
    timeout: float,
    allowed_statuses: set[int] | None = None,
    **kwargs: Any,
) -> tuple[int, dict[str, Any] | list[Any]]:
    response = session.request(method, url, timeout=timeout, **kwargs)
    _raise_for_status(response, step=step, allowed_statuses=allowed_statuses)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step} returned non-JSON payload: {response.text[:500]}") from exc
    if not isinstance(payload, (dict, list)):
        raise RuntimeError(f"{step} returned unexpected payload type: {type(payload).__name__}")
    return response.status_code, payload


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    _, health = call_json(
        session,
        method="GET",
        url=f"{base_url}/health",
        step="health",
        timeout=args.timeout_seconds,
    )

    signup_status, signup_payload = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/clinician/signup",
        step="clinician signup",
        timeout=args.timeout_seconds,
        allowed_statuses={400, 409},
        json={
            "email": args.clinician_email,
            "password": args.clinician_password,
            "full_name": args.clinician_name,
            "registration_number": args.clinician_registration,
        },
    )

    _, clinician_login = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/clinician/login",
        step="clinician login",
        timeout=args.timeout_seconds,
        json={"email": args.clinician_email, "password": args.clinician_password},
    )
    if not isinstance(clinician_login, dict):
        raise RuntimeError("clinician login returned unexpected payload")
    clinician_token = str(clinician_login.get("access_token") or "").strip()
    if not clinician_token:
        raise RuntimeError("clinician login succeeded but no access_token was returned")

    _, patient_login = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/auth/login",
        step="patient login",
        timeout=args.timeout_seconds,
        json={"email": args.patient_email, "password": args.patient_password},
    )
    if not isinstance(patient_login, dict):
        raise RuntimeError("patient login returned unexpected payload")
    patient_token = str(patient_login.get("access_token") or "").strip()
    if not patient_token:
        raise RuntimeError("patient login succeeded but no access_token was returned")

    _, patients_payload = call_json(
        session,
        method="GET",
        url=f"{base_url}/api/v1/patients/?limit=100",
        step="list patients",
        timeout=args.timeout_seconds,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    if not isinstance(patients_payload, list) or not patients_payload:
        raise RuntimeError("No patient available for clinician copilot smoke test")
    patient_id = args.patient_id or int(patients_payload[0]["id"])

    access_request_status, access_request_payload = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/clinician/access/request",
        step="request clinician access",
        timeout=args.timeout_seconds,
        allowed_statuses={400},
        headers={"Authorization": f"Bearer {clinician_token}"},
        json={"patient_id": patient_id},
    )

    _, requests_payload = call_json(
        session,
        method="GET",
        url=f"{base_url}/api/v1/patient/access/requests",
        step="list patient access requests",
        timeout=args.timeout_seconds,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    if not isinstance(requests_payload, list):
        raise RuntimeError("patient access requests returned unexpected payload")

    matched_request = next(
        (
            item
            for item in requests_payload
            if item.get("patient_id") == patient_id
            and item.get("clinician_email") == args.clinician_email
        ),
        None,
    )
    if matched_request is None:
        raise RuntimeError(f"No access request found for clinician {args.clinician_email}")

    grant_payload: dict[str, Any] | None = None
    if matched_request.get("status") == "pending":
        _, grant_response = call_json(
            session,
            method="POST",
            url=f"{base_url}/api/v1/patient/access/grant",
            step="grant clinician access",
            timeout=args.timeout_seconds,
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"grant_id": matched_request["grant_id"]},
        )
        if not isinstance(grant_response, dict):
            raise RuntimeError("grant response returned unexpected payload")
        grant_payload = grant_response

    _, create_run_payload = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/clinician/agent/runs",
        step="create clinician copilot run",
        timeout=args.timeout_seconds,
        headers={"Authorization": f"Bearer {clinician_token}"},
        json={
            "patient_id": patient_id,
            "template": args.template,
            "prompt": args.prompt,
        },
    )
    if not isinstance(create_run_payload, dict):
        raise RuntimeError("create clinician copilot run returned unexpected payload")
    run_id = int(create_run_payload["id"])

    _, list_runs_payload = call_json(
        session,
        method="GET",
        url=f"{base_url}/api/v1/clinician/agent/runs?patient_id={patient_id}",
        step="list clinician copilot runs",
        timeout=args.timeout_seconds,
        headers={"Authorization": f"Bearer {clinician_token}"},
    )

    _, get_run_payload = call_json(
        session,
        method="GET",
        url=f"{base_url}/api/v1/clinician/agent/runs/{run_id}",
        step="get clinician copilot run",
        timeout=args.timeout_seconds,
        headers={"Authorization": f"Bearer {clinician_token}"},
    )

    summary = {
        "base_url": base_url,
        "health": health,
        "signup_status": signup_status,
        "signup_payload": signup_payload,
        "patient_id": patient_id,
        "access_request_status": access_request_status,
        "access_request_payload": access_request_payload,
        "matched_request": matched_request,
        "grant_payload": grant_payload,
        "created_run": create_run_payload,
        "listed_runs_count": len(list_runs_payload) if isinstance(list_runs_payload, list) else None,
        "fetched_run": get_run_payload,
    }

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
