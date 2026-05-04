from __future__ import annotations

import argparse
import json

from scripts.evaluate_speech_transcription import load_examples, summarize_rows


def test_load_examples_resolves_manifest_relative_audio_paths(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    audio_path = audio_dir / "patient.wav"
    audio_path.write_bytes(b"RIFF")
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "id": "patient-1",
                "audio_path": "audio/patient.wav",
                "reference": "what are my recent labs",
                "role": "patient",
                "environment": "quiet",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    examples = load_examples(argparse.Namespace(audio=[], manifest=manifest_path))

    assert len(examples) == 1
    assert examples[0].audio_path == audio_path.resolve()
    assert examples[0].metadata == {"role": "patient", "environment": "quiet"}


def test_summarize_rows_groups_by_role_and_environment():
    summary = summarize_rows(
        [
            {
                "id": "one",
                "confidence": 0.9,
                "word_error_rate": 0.1,
                "metadata": {"role": "patient", "environment": "quiet"},
            },
            {
                "id": "two",
                "confidence": 0.7,
                "word_error_rate": 0.3,
                "metadata": {"role": "clinician", "environment": "clinic"},
            },
        ]
    )

    assert summary["example_count"] == 2
    assert summary["average_word_error_rate"] == 0.2
    assert summary["average_confidence"] == 0.8
    assert summary["by_role"]["patient"]["average_word_error_rate"] == 0.1
    assert summary["by_environment"]["clinic"]["average_confidence"] == 0.7
