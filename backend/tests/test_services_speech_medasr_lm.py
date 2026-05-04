from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.speech.medasr_lm import (
    BeamScoreSummary,
    LasrCtcBeamSearchDecoder,
    estimate_beam_confidence,
)


def test_estimate_beam_confidence_uses_top_beam_posterior_mass():
    confidence = estimate_beam_confidence(
        [
            BeamScoreSummary(
                text="latest hemoglobin result",
                logit_score=-4.2,
                lm_score=-12.0,
            ),
            BeamScoreSummary(
                text="latest hemoglobin results",
                logit_score=-4.8,
                lm_score=-13.8,
            ),
            BeamScoreSummary(
                text="latest hemoglobin",
                logit_score=-5.0,
                lm_score=-15.5,
            ),
        ]
    )

    assert confidence == pytest.approx(0.8364727049)


def test_estimate_beam_confidence_requires_multiple_beams():
    confidence = estimate_beam_confidence(
        [
            BeamScoreSummary(
                text="latest hemoglobin result",
                logit_score=-4.2,
                lm_score=-12.0,
            )
        ]
    )

    assert confidence is None


def test_decode_beams_records_last_beam_summaries():
    @dataclass(frozen=True)
    class FakeBeam:
        text: str
        last_lm_state: object | None
        text_frames: list[object]
        logit_score: float
        lm_score: float

    decoder = LasrCtcBeamSearchDecoder.__new__(LasrCtcBeamSearchDecoder)
    decoder._decoder = type(
        "FakeDecoder",
        (),
        {
            "decode_beams": lambda self, *_args, **_kwargs: [
                FakeBeam(
                    text="latest#hemoglobin</s>",
                    last_lm_state=None,
                    text_frames=[],
                    logit_score=-4.2,
                    lm_score=-12.0,
                ),
                FakeBeam(
                    text="latest#hemoglobin#results",
                    last_lm_state=None,
                    text_frames=[],
                    logit_score=-4.8,
                    lm_score=-13.8,
                ),
            ]
        },
    )()
    decoder.last_beam_summaries = ()

    beams = decoder.decode_beams()

    assert [beam.text for beam in beams] == [
        "latest hemoglobin",
        "latest hemoglobin results",
    ]
    assert decoder.last_beam_summaries == (
        BeamScoreSummary(
            text="latest hemoglobin",
            logit_score=-4.2,
            lm_score=-12.0,
        ),
        BeamScoreSummary(
            text="latest hemoglobin results",
            logit_score=-4.8,
            lm_score=-13.8,
        ),
    )
