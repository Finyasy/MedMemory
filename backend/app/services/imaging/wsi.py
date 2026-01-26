"""Helpers for histopathology WSI patch interpretation."""

from dataclasses import dataclass

from app.services.imaging.volume import VolumeMontageResult, build_volume_montage


@dataclass
class WsiMontageResult(VolumeMontageResult):
    """WSI montage metadata (alias of VolumeMontageResult)."""


def build_wsi_montage(
    patch_images: list[bytes],
    sample_count: int = 12,
    tile_size: int = 256,
) -> WsiMontageResult:
    """Build a montage from WSI patches."""
    result = build_volume_montage(
        slice_images=patch_images,
        sample_count=sample_count,
        tile_size=tile_size,
    )
    return WsiMontageResult(
        montage_bytes=result.montage_bytes,
        total_slices=result.total_slices,
        sampled_indices=result.sampled_indices,
        grid=result.grid,
        tile_size=result.tile_size,
    )
