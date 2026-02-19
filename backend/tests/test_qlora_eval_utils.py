from scripts.qlora_eval_utils import (
    compute_generation_metrics,
    extract_facts,
    normalize_text,
    token_f1,
)


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  A   B\nC  ") == "a b c"


def test_token_f1_exact_match():
    assert token_f1("Blood pressure is 120 mmHg", "Blood pressure is 120 mmHg") == 1.0


def test_extract_facts_finds_measurements_dates_and_polarity():
    facts = extract_facts("BP 120 mmHg on 01/10/2026; HIV: Non-Reactive.")
    assert "120 mmhg" in facts
    assert "01/10/2026" in facts
    assert "non-reactive" in facts


def test_compute_generation_metrics_has_expected_bounds():
    refs = [
        "Hemoglobin is 10.1 g/dL and TB screening is positive.",
        "Blood pressure is 120 mmHg.",
    ]
    preds = [
        "Hemoglobin is 10.1 g/dL and TB screening is positive.",
        "Blood pressure is 130 mmHg.",
    ]
    metrics = compute_generation_metrics(preds, refs)
    assert 0.0 <= metrics.exact_match <= 1.0
    assert 0.0 <= metrics.token_f1 <= 1.0
    assert 0.0 <= metrics.fact_precision <= 1.0
    assert 0.0 <= metrics.fact_recall <= 1.0
    assert 0.0 <= metrics.hallucination_rate <= 1.0
    assert metrics.n_examples == 2
