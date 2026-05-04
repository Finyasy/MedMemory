"""Speech asset storage abstraction."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.config import settings


@dataclass(frozen=True)
class SpeechAssetDescriptor:
    asset_id: str
    relative_path: str
    absolute_path: Path
    audio_url: str | None = None
    duration_ms: int | None = None
    mime_type: str = "audio/wav"
    metadata: dict[str, Any] = field(default_factory=dict)


class SpeechStorageService:
    """Storage seam for generated speech assets."""

    _instance: SpeechStorageService | None = None

    @classmethod
    def get_instance(cls) -> SpeechStorageService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, *, assets_root: Path | None = None) -> None:
        self.assets_root = self._resolve_assets_root(
            assets_root or settings.speech_synthesis_assets_dir
        )

    @staticmethod
    def _resolve_assets_root(path: Path) -> Path:
        backend_dir = Path(__file__).resolve().parents[3]
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (backend_dir / candidate).resolve()
        return candidate

    def _resolve_relative_path(self, relative_path: str) -> Path:
        raw_path = Path(relative_path)
        if raw_path.is_absolute():
            raise ValueError("Speech asset paths must be relative.")
        resolved = (self.assets_root / raw_path).resolve()
        root = self.assets_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("Speech asset path escapes the configured assets directory.")
        return resolved

    @staticmethod
    def _metadata_path(audio_path: Path) -> Path:
        return audio_path.with_suffix(f"{audio_path.suffix}.json")

    @staticmethod
    def _audio_url(asset_id: str) -> str:
        return f"{settings.api_prefix}/speech/assets/{quote(asset_id, safe='/')}"

    async def get_asset_descriptor(
        self,
        *,
        asset_id: str,
    ) -> SpeechAssetDescriptor | None:
        audio_path = self._resolve_relative_path(asset_id)
        metadata_path = self._metadata_path(audio_path)
        if not audio_path.exists():
            return None
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            metadata = await asyncio.to_thread(
                lambda: json.loads(metadata_path.read_text(encoding="utf-8"))
            )
        duration_ms = metadata.get("duration_ms")
        mime_type = str(metadata.get("mime_type") or "audio/wav")
        return SpeechAssetDescriptor(
            asset_id=asset_id,
            relative_path=asset_id,
            absolute_path=audio_path,
            audio_url=self._audio_url(asset_id),
            duration_ms=int(duration_ms) if isinstance(duration_ms, int) else None,
            mime_type=mime_type,
            metadata=metadata,
        )

    async def save_generated_audio(
        self,
        *,
        asset_id: str,
        relative_path: str,
        audio_bytes: bytes,
        duration_ms: int | None = None,
        mime_type: str = "audio/wav",
        metadata: dict[str, Any] | None = None,
    ) -> SpeechAssetDescriptor:
        audio_path = self._resolve_relative_path(relative_path)
        metadata_path = self._metadata_path(audio_path)
        descriptor = await self.get_asset_descriptor(asset_id=asset_id)
        if descriptor is not None:
            return descriptor

        payload = {
            **(metadata or {}),
            "asset_id": asset_id,
            "relative_path": relative_path,
            "duration_ms": duration_ms,
            "mime_type": mime_type,
        }

        def write_files() -> None:
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(audio_bytes)
            metadata_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(write_files)
        return SpeechAssetDescriptor(
            asset_id=asset_id,
            relative_path=relative_path,
            absolute_path=audio_path,
            audio_url=self._audio_url(asset_id),
            duration_ms=duration_ms,
            mime_type=mime_type,
            metadata=payload,
        )

    async def read_generated_audio(
        self,
        *,
        asset_id: str,
    ) -> SpeechAssetDescriptor:
        descriptor = await self.get_asset_descriptor(asset_id=asset_id)
        if descriptor is None:
            raise FileNotFoundError(asset_id)
        return descriptor
