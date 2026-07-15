#!/usr/bin/env python3
"""Run a live speech-to-chat smoke test against a local MedMemory backend.

Usage:
    cd backend
    uv run python scripts/run_speech_chat_smoke.py \
      --audio /tmp/patient-question.wav \
      --patient-id 10
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
        "--email",
        default=os.getenv("E2E_EMAIL", "demo@medmemory.ai"),
        help="Patient login email.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("E2E_PASSWORD", "demo-password"),
        help="Patient login password.",
    )
    parser.add_argument(
        "--audio",
        type=Path,
        required=True,
        help="Audio clip to transcribe.",
    )
    parser.add_argument(
        "--patient-id",
        type=int,
        required=True,
        help="Patient id used for speech and chat requests.",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Speech transcription language. Current production path supports only English.",
    )
    parser.add_argument(
        "--question",
        help="Optional explicit question for /chat/ask. Defaults to the live transcript.",
    )
    parser.add_argument(
        "--clinician-mode",
        action="store_true",
        help="Send clinician_mode=true to speech and chat requests.",
    )
    parser.add_argument(
        "--skip-chat",
        action="store_true",
        help="Only verify login and speech transcription.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="HTTP timeout for each request.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for the smoke summary JSON.",
    )
    return parser.parse_args()


def _raise_for_status(response: requests.Response, *, step: str) -> None:
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
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, url, timeout=timeout, **kwargs)
    _raise_for_status(response, step=step)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step} returned non-JSON payload: {response.text[:500]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{step} returned unexpected payload type: {type(payload).__name__}")
    return payload


def main() -> None:
    args = parse_args()
    audio_path = args.audio.expanduser().resolve()
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    health = call_json(
        session,
        method="GET",
        url=f"{base_url}/health",
        step="health check",
        timeout=args.timeout_seconds,
    )
    speech_health = call_json(
        session,
        method="GET",
        url=f"{base_url}/health/speech",
        step="speech health check",
        timeout=args.timeout_seconds,
    )
    login_payload = call_json(
        session,
        method="POST",
        url=f"{base_url}/api/v1/auth/login",
        step="login",
        timeout=args.timeout_seconds,
        json={"email": args.email, "password": args.password},
    )
    access_token = str(login_payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("login succeeded but no access_token was returned")
    session.headers["Authorization"] = f"Bearer {access_token}"

    me_payload = call_json(
        session,
        method="GET",
        url=f"{base_url}/api/v1/auth/me",
        step="auth/me",
        timeout=args.timeout_seconds,
    )

    with audio_path.open("rb") as handle:
        transcription_payload = call_json(
            session,
            method="POST",
            url=f"{base_url}/api/v1/speech/transcribe",
            step="speech transcription",
            timeout=args.timeout_seconds,
            files={"audio": (audio_path.name, handle, "audio/wav")},
            data={
                "patient_id": str(args.patient_id),
                "clinician_mode": str(args.clinician_mode).lower(),
                "language": args.language,
            },
        )

    transcript = str(transcription_payload.get("transcript") or "").strip()
    if not transcript:
        raise RuntimeError("speech transcription returned an empty transcript")

    summary: dict[str, Any] = {
        "base_url": base_url,
        "health": health,
        "speech_health": speech_health,
        "auth_me": me_payload,
        "transcription": transcription_payload,
    }

    if not args.skip_chat:
        chat_payload = call_json(
            session,
            method="POST",
            url=f"{base_url}/api/v1/chat/ask",
            step="chat ask",
            timeout=args.timeout_seconds,
            json={
                "question": args.question or transcript,
                "patient_id": args.patient_id,
                "input_mode": "voice",
                "input_language": args.language,
                "output_language": "en",
            },
        )
        summary["chat"] = chat_payload

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
