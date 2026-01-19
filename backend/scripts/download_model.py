#!/usr/bin/env python3
"""
Download MedGemma model for local use (and optionally smoke-test loading).

Optimizations:
- Uses MPS on Apple Silicon (instead of CPU)
- Uses inference_mode for lower overhead
- Prefers bf16 on MPS when supported
- Pins optional revision for reproducibility
- Warns clearly when 4-bit is requested without CUDA
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from huggingface_hub import HfApi, HfFolder, snapshot_download
from huggingface_hub.errors import HfHubHTTPError
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig


def pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    # Apple Silicon / Metal
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def supports_mps_bf16() -> bool:
    if not (getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()):
        return False
    try:
        _ = torch.zeros(1, device="mps", dtype=torch.bfloat16)
        return True
    except (TypeError, RuntimeError):
        return False


def pick_dtype(device: str) -> torch.dtype:
    # On Apple Silicon, prefer bf16 when supported; otherwise use fp16.
    if device == "mps":
        return torch.bfloat16 if supports_mps_bf16() else torch.float16
    if device == "cuda":
        return torch.float16
    return torch.float32


def torch_version_at_least(required: str) -> bool:
    def parse(version: str) -> tuple[int, ...]:
        core = version.split("+", maxsplit=1)[0]
        parts = core.split(".")
        nums = []
        for part in parts:
            try:
                nums.append(int(part))
            except ValueError:
                break
        return tuple(nums)

    return parse(torch.__version__) >= parse(required)


def parse_model_size_b(model_id: str) -> Optional[float]:
    lower = model_id.lower()
    parts = lower.replace("-", " ").replace("_", " ").split()
    for part in parts:
        if part.endswith("b"):
            value = part[:-1]
            try:
                return float(value)
            except ValueError:
                continue
    return None


class Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str) -> int:
        count = 0
        for stream in self._streams:
            count = stream.write(data)
            stream.flush()
        return count

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def resolve_hf_token(provided_token: Optional[str]) -> Optional[str]:
    return provided_token or HfFolder.get_token()


def require_hf_auth(model_id: str, token: Optional[str]) -> str:
    if not token:
        print(
            "\n❌ HF_TOKEN not found. This model is gated.\n"
            "   1) Accept the model terms on Hugging Face:\n"
            f"      https://huggingface.co/{model_id}\n"
            "   2) Create a Hugging Face access token:\n"
            "      https://huggingface.co/settings/tokens\n"
            "   3) Export it, e.g.:\n"
            "      export HF_TOKEN=hf_your_token_here\n"
            "      python backend/scripts/download_model.py --model-id "
            f"{model_id}\n"
        )
        sys.exit(1)

    api = HfApi()
    try:
        api.whoami(token=token)
    except HfHubHTTPError:
        print(
            "\n❌ HF_TOKEN is invalid or does not grant access to this model.\n"
            "   Verify your token and ensure you've accepted the model terms.\n"
        )
        sys.exit(1)
    return token


def download_model(
    model_id: str,
    output_dir: Path,
    hf_token: Optional[str],
    revision: Optional[str] = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_id,
        local_dir=str(output_dir),
        token=hf_token,
        revision=revision,
    )
    return output_dir


def smoke_test_load(
    model_path: Path,
    device: str,
    dtype: torch.dtype,
    quantize_4bit: bool,
) -> None:
    print(f"🔧 Device: {device} | DType: {dtype}")

    processor = AutoProcessor.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        use_fast=True,  # Use fast processor to avoid deprecation warning
    )

    quant_cfg = None
    if quantize_4bit:
        if device != "cuda":
            print("⚠️  4-bit quantization requested but CUDA is not available. Skipping 4-bit.")
        else:
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )

    # Loading strategy:
    # - CUDA: device_map="auto" works well
    # - MPS: move to MPS explicitly after load (device_map isn't consistently supported)
    model = AutoModelForImageTextToText.from_pretrained(
        str(model_path),
        device_map="auto" if device == "cuda" else None,
        dtype=dtype,  # Use dtype instead of torch_dtype (deprecated)
        quantization_config=quant_cfg,
        trust_remote_code=True,
        low_cpu_mem_usage=True,  # reduces peak RAM during load
    )

    if device == "mps":
        model = model.to("mps")
    elif device == "cpu":
        model = model.to("cpu")

    # Smoke test generation (text-only)
    inputs = processor(text="Hello", return_tensors="pt")

    # Move tensors to the right device
    inputs = {k: v.to(model.device) for k, v in inputs.items() if hasattr(v, "to")}

    # Speed + memory optimization during inference
    with torch.inference_mode():
        _ = model.generate(**inputs, max_new_tokens=8, do_sample=False)

    print("✅ Smoke test passed: model can load and generate.")


def _load_hf_token_from_env() -> Optional[str]:
    """Load HF_TOKEN from .env file or environment."""
    # First check environment
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    
    # Try to load from .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("HF_TOKEN=") and not line.startswith("#"):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        return token
        except Exception:
            pass
    
    return None


def main():
    # Load HF_TOKEN from .env or environment
    hf_token_default = _load_hf_token_from_env()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="google/medgemma-1.5-4b-it")
    parser.add_argument("--output-dir", type=Path, default=Path("models/medgemma-1.5-4b-it"))
    parser.add_argument("--hf-token", default=hf_token_default, help="Hugging Face token (or set HF_TOKEN env var)")
    parser.add_argument("--revision", default=None, help="Optional HF revision/commit hash for reproducibility")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--skip-smoke-test", action="store_true")
    parser.add_argument("--quantize-4bit", action="store_true")
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default="auto")
    args = parser.parse_args()

    if os.getenv("CI") and not args.revision:
        print("❌ CI mode detected. Please set --revision explicitly for reproducible downloads.")
        sys.exit(1)

    hf_token = resolve_hf_token(args.hf_token)
    hf_token = require_hf_auth(args.model_id, hf_token)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / "download.log"
    log_file = log_path.open("a", encoding="utf-8")
    tee = Tee(sys.stdout, log_file)
    sys.stdout = tee
    sys.stderr = tee

    print(f"📦 Downloading {args.model_id} → {args.output_dir}")
    print(f"📝 Download log: {log_path}")

    try:
        download_model(args.model_id, args.output_dir, hf_token, revision=args.revision)
    except HfHubHTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in {401, 403}:
            print(
                "\n❌ Unable to access the model. It is gated and requires approval.\n"
                "   1) Accept the model terms on Hugging Face:\n"
                f"      https://huggingface.co/{args.model_id}\n"
                "   2) Ensure your HF_TOKEN has access.\n"
            )
        raise

    print("✅ Download complete.")

    api = HfApi()
    info = api.model_info(args.model_id, revision=args.revision, token=hf_token)
    resolved_revision = info.sha

    metadata = {
        "model_id": args.model_id,
        "revision": args.revision,
        "resolved_revision": resolved_revision,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = args.output_dir / "model_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"🧾 Resolved revision: {resolved_revision}")
    print(f"🧾 Metadata written: {metadata_path}")

    device = pick_device(args.device)
    dtype = pick_dtype(device)
    if device == "mps" and dtype == torch.float16:
        print("⚠️  MPS bf16 not supported in this PyTorch build; falling back to fp16.")
    model_size_b = parse_model_size_b(args.model_id)
    if device == "cpu" and model_size_b and model_size_b >= 4:
        print(
            "\n⚠️  CPU mode detected for a >=4B model. Expect very slow performance.\n"
            "    Recommended: Apple Silicon (MPS) or a CUDA GPU.\n"
        )

    smoke_test_requested = args.smoke_test and not args.skip_smoke_test
    if smoke_test_requested and not torch_version_at_least("2.6"):
        print(
            "\n⚠️  Smoke test skipped: this model requires torch>=2.6 for generation.\n"
            f"    Current torch version: {torch.__version__}\n"
            "    Upgrade PyTorch or rerun without --smoke-test.\n"
        )
        smoke_test_requested = False
    if smoke_test_requested:
        smoke_test_load(args.output_dir, device, dtype, args.quantize_4bit)
    else:
        print("Skipping model load smoke test (CI / headless mode).")

    quant_active = args.quantize_4bit and device == "cuda"
    quant_note = "active" if quant_active else ("skipped (CUDA required)" if args.quantize_4bit else "disabled")
    summary = (
        "\n==== Model Download Summary ====\n"
        f"Model ID: {args.model_id}\n"
        f"Local path: {args.output_dir}\n"
        f"Resolved revision: {resolved_revision}\n"
        f"Device: {device}\n"
        f"DType: {dtype}\n"
        f"Quantization: {quant_note}\n"
        f"Smoke test: {'run' if smoke_test_requested else 'skipped'}\n"
        "================================\n"
    )
    print(summary)


if __name__ == "__main__":
    main()
