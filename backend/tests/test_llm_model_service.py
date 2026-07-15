from __future__ import annotations

import builtins
import sys
import types
from types import SimpleNamespace

import pytest
import torch

import app.services.llm.model as model_module
from app.config import settings
from app.services.llm.model import LLMResponse, LLMService


def test_resolve_mlx_model_name_prefers_quantized_dir(tmp_path, monkeypatch):
    quantized_dir = tmp_path / "mlx-quantized"
    quantized_dir.mkdir()
    (quantized_dir / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        settings,
        "llm_mlx_quantized_model_path",
        str(quantized_dir),
        raising=False,
    )

    service = LLMService(model_name="google/medgemma")

    assert service._resolve_mlx_model_name() == str(quantized_dir)


def test_load_mlx_runtime_disables_backend_when_import_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mlx_lm":
            raise ModuleNotFoundError("No module named 'mlx_lm'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    service = LLMService(model_name="dummy", device="mps")
    service.use_mlx_text_backend = True

    assert service._load_mlx_runtime() is False
    assert service.use_mlx_text_backend is False
    assert "No module named 'mlx_lm'" in (service._mlx_disabled_reason or "")


def test_load_mlx_runtime_caches_loaded_runtime(monkeypatch):
    fake_module = types.ModuleType("mlx_lm")
    load_calls: list[str] = []

    def fake_load(source: str):
        load_calls.append(source)
        return "mlx-model", "mlx-tokenizer"

    fake_module.load = fake_load
    monkeypatch.setitem(sys.modules, "mlx_lm", fake_module)

    service = LLMService(model_name="dummy", device="mps")
    service.use_mlx_text_backend = True

    assert service._load_mlx_runtime() is True
    assert service._mlx_model == "mlx-model"
    assert service._mlx_tokenizer == "mlx-tokenizer"
    assert service._load_mlx_runtime() is True
    assert len(load_calls) == 1


def test_load_mlx_runtime_falls_back_when_model_load_fails(monkeypatch):
    fake_module = types.ModuleType("mlx_lm")

    def fake_load(_source: str):
        raise RuntimeError("broken quantized model")

    fake_module.load = fake_load
    monkeypatch.setitem(sys.modules, "mlx_lm", fake_module)

    service = LLMService(model_name="dummy", device="mps")
    service.use_mlx_text_backend = True

    assert service._load_mlx_runtime() is False
    assert service.use_mlx_text_backend is False
    assert "broken quantized model" in (service._mlx_disabled_reason or "")


def test_load_processor_respects_torchvision_availability(monkeypatch):
    observed: list[dict] = []

    def fake_from_pretrained(model_name: str, **kwargs):
        observed.append({"model_name": model_name, **kwargs})
        return "processor"

    monkeypatch.setattr(model_module.AutoProcessor, "from_pretrained", fake_from_pretrained)
    monkeypatch.setattr(model_module.importlib.util, "find_spec", lambda name: object())

    service = LLMService(model_name="dummy")
    assert service._load_processor() == "processor"

    assert observed[-1]["model_name"] == service.model_name
    assert observed[-1]["use_fast"] is True
    assert observed[-1]["trust_remote_code"] is True

    observed.clear()
    monkeypatch.setattr(model_module.importlib.util, "find_spec", lambda name: None)
    service = LLMService(model_name="dummy")
    service.use_local_model = True
    assert service._load_processor() == "processor"
    assert observed[-1]["use_fast"] is False
    assert observed[-1]["local_files_only"] is True


@pytest.mark.anyio
async def test_generate_prefers_mlx_runtime_when_available(monkeypatch):
    service = LLMService(model_name="dummy", device="mps")
    service.use_mlx_text_backend = True

    async def fake_generate_with_mlx(**kwargs):
        assert kwargs["prompt"] == "Hello"
        return LLMResponse(
            text="Hi",
            tokens_generated=1,
            tokens_input=1,
            generation_time_ms=1.0,
        )

    monkeypatch.setattr(service, "_load_mlx_runtime", lambda: True)
    monkeypatch.setattr(service, "_generate_with_mlx", fake_generate_with_mlx)

    response = await service.generate("Hello")

    assert response.text == "Hi"


def test_build_prompt_prefers_chat_template_and_normalizes_roles():
    captured_messages: list[dict] = []

    class DummyTokenizer:
        chat_template = "template"

        def apply_chat_template(self, messages, tokenize, add_generation_prompt):
            captured_messages.extend(messages)
            assert tokenize is False
            assert add_generation_prompt is True
            return "templated-prompt"

    service = LLMService(model_name="dummy")
    service._processor = SimpleNamespace(tokenizer=DummyTokenizer())

    prompt = service._build_prompt(
        prompt="Need a summary",
        system_prompt="Be concise",
        conversation_history=[
            {"role": "moderator", "content": "normalize me"},
            {"role": "assistant", "content": "prior answer"},
        ],
    )

    assert prompt == "templated-prompt"
    assert captured_messages[1]["role"] == "user"
    assert captured_messages[-1]["content"] == "Need a summary"


def test_image_prompt_helpers_and_multimodal_validation():
    tokenizer = SimpleNamespace(image_token_id=7)
    service = LLMService(model_name="dummy")
    service._processor = SimpleNamespace(
        image_token="<med-image>",
        tokenizer=tokenizer,
    )

    assert service._ensure_image_token("Review this scan") == "<med-image>\nReview this scan"
    assert service._ensure_image_token("<med-image>\nReview this scan") == "<med-image>\nReview this scan"

    service._validate_multimodal_inputs(
        inputs={
            "pixel_values": torch.zeros((1, 2, 3, 4, 4)),
            "input_ids": torch.tensor([[7, 1, 7]]),
        },
        expected_image_count=2,
        mode="multi-image",
    )

    with pytest.raises(RuntimeError, match="missing pixel_values"):
        service._validate_multimodal_inputs(
            inputs={"input_ids": torch.tensor([[7]])},
            expected_image_count=1,
            mode="single-image",
        )

    with pytest.raises(RuntimeError, match="fewer image tensors than expected"):
        service._validate_multimodal_inputs(
            inputs={
                "pixel_values": torch.zeros((1, 1, 3, 4, 4)),
                "input_ids": torch.tensor([[7, 7]]),
            },
            expected_image_count=2,
            mode="multi-image",
        )


def test_get_model_info_reports_loaded_mlx_runtime(monkeypatch):
    class DummyTokenizer:
        def __len__(self):
            return 9

    service = LLMService(
        model_name="dummy",
        device="cuda",
        load_in_4bit=True,
        load_in_8bit=True,
    )
    service._processor = SimpleNamespace(tokenizer=DummyTokenizer())
    service._mlx_model = object()
    service._model = object()
    service.use_mlx_text_backend = True

    monkeypatch.setattr(model_module.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(model_module.torch.cuda, "memory_allocated", lambda: 3_000_000_000)

    info = service.get_model_info()

    assert info["runtime"] == "mlx"
    assert info["quantization"]["4bit"] is True
    assert info["quantization"]["8bit"] is True
    assert info["gpu_memory_gb"] == 3.0
