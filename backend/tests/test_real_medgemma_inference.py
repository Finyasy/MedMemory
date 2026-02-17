from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import settings
from app.services.llm.model import LLMService


def _resolve_model_path() -> Path | None:
    configured = settings.llm_model_path
    if configured is None:
        return None
    path = Path(configured)
    if path.is_absolute():
        return path
    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / path).resolve()


@pytest.mark.anyio
async def test_real_medgemma_inference_smoke():
    """Opt-in smoke test that executes a real local model generation."""
    if os.getenv("RUN_REAL_MEDGEMMA_INFERENCE") != "1":
        pytest.skip("Set RUN_REAL_MEDGEMMA_INFERENCE=1 to run real model inference.")

    model_path = _resolve_model_path()
    if model_path is None:
        pytest.skip("LLM_MODEL_PATH is not configured for local real-inference smoke test.")
    if not model_path.exists():
        pytest.skip(f"Model path not found for smoke test: {model_path}")

    # Ensure this test does not reuse mocked singleton state.
    LLMService._instance = None
    try:
        llm = LLMService.get_instance()
        response = await llm.generate(
            prompt=(
                "MedMemory real inference smoke check. "
                "Respond with one concise sentence."
            ),
            max_new_tokens=64,
            do_sample=False,
            temperature=0.0,
            top_p=1.0,
        )
        info = llm.get_model_info()

        assert (response.text or "").strip()
        assert response.tokens_generated >= 1
        assert info["is_loaded"] is True
    finally:
        LLMService._instance = None

