"""Helpers for basic 3D volume interpretation using 2D slice montages."""

import io
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps


@dataclass
class VolumeMontageResult:
    montage_bytes: bytes
    total_slices: int
    sampled_indices: list[int]
    grid: tuple[int, int]
    tile_size: tuple[int, int]


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def choose_sample_indices(total: int, sample_count: int) -> list[int]:
    """Select evenly spaced indices across a volume."""
    if total <= 0:
        return []
    if sample_count <= 1 or total == 1:
        return [0]
    sample_count = min(sample_count, total)
    step = (total - 1) / (sample_count - 1)
    indices = [int(round(i * step)) for i in range(sample_count)]
    # Ensure strictly increasing, clamp to bounds.
    deduped: list[int] = []
    last = -1
    for idx in indices:
        idx = min(max(idx, 0), total - 1)
        if idx <= last:
            idx = min(last + 1, total - 1)
        if idx != last:
            deduped.append(idx)
            last = idx
    return deduped


def build_volume_montage(
    slice_images: Sequence[bytes],
    sample_count: int = 9,
    tile_size: int = 256,
) -> VolumeMontageResult:
    """Create a montage from volume slices for VLM input."""
    total_slices = len(slice_images)
    if total_slices == 0:
        raise ValueError("No slices provided.")

    sampled_indices = choose_sample_indices(total_slices, sample_count)
    if not sampled_indices:
        raise ValueError("Unable to sample slices.")

    processed = [
        _prepare_slice_image(
            Image.open(io.BytesIO(slice_images[idx])).convert("L"), tile_size
        )
        for idx in sampled_indices
    ]
    count = len(processed)
    cols = max(1, int(math.ceil(math.sqrt(count))))
    rows = max(1, int(math.ceil(count / cols)))
    montage = Image.new("L", (cols * tile_size, rows * tile_size), color=0)

    for idx, tile in enumerate(processed):
        row = idx // cols
        col = idx % cols
        montage.paste(tile, (col * tile_size, row * tile_size))

    output = io.BytesIO()
    montage.convert("RGB").save(output, format="PNG")

    return VolumeMontageResult(
        montage_bytes=output.getvalue(),
        total_slices=total_slices,
        sampled_indices=sampled_indices,
        grid=(rows, cols),
        tile_size=(tile_size, tile_size),
    )


def filter_image_filenames(filenames: Iterable[str]) -> list[str]:
    """Keep only supported image filenames, preserving order."""
    allowed = []
    for name in filenames:
        lower = name.lower()
        if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
            allowed.append(name)
    return allowed


def build_volume_montage_from_array(
    volume: np.ndarray,
    sample_count: int = 9,
    tile_size: int = 256,
) -> VolumeMontageResult:
    """Create a montage from a 3D volume array."""
    if volume.ndim != 3:
        raise ValueError("Volume must be 3D (H, W, S).")
    total_slices = volume.shape[2]
    sampled_indices = choose_sample_indices(total_slices, sample_count)
    if not sampled_indices:
        raise ValueError("Unable to sample slices.")

    processed = [
        _prepare_slice_image(
            Image.fromarray(_normalize_to_uint8(volume[:, :, idx])).convert("L"),
            tile_size,
        )
        for idx in sampled_indices
    ]
    count = len(processed)
    cols = max(1, int(math.ceil(math.sqrt(count))))
    rows = max(1, int(math.ceil(count / cols)))
    montage = Image.new("L", (cols * tile_size, rows * tile_size), color=0)

    for idx, tile in enumerate(processed):
        row = idx // cols
        col = idx % cols
        montage.paste(tile, (col * tile_size, row * tile_size))

    output = io.BytesIO()
    montage.convert("RGB").save(output, format="PNG")

    return VolumeMontageResult(
        montage_bytes=output.getvalue(),
        total_slices=total_slices,
        sampled_indices=sampled_indices,
        grid=(rows, cols),
        tile_size=(tile_size, tile_size),
    )


def load_nifti_volume(nifti_bytes: bytes) -> np.ndarray:
    """Load a NIfTI volume into a 3D numpy array."""
    import tempfile

    import nibabel as nib

    with tempfile.NamedTemporaryFile(suffix=".nii.gz") as tmp:
        tmp.write(nifti_bytes)
        tmp.flush()
        image = nib.load(tmp.name)
        data = np.asarray(image.dataobj)

    if data.ndim == 4:
        data = data[..., 0]
    if data.ndim != 3:
        raise ValueError("NIfTI volume must be 3D.")
    return data.astype(np.float32)


def load_dicom_volume(dicom_bytes_list: Sequence[bytes]) -> np.ndarray:
    """Load a DICOM series into a 3D numpy array."""
    import pydicom

    slices: list[tuple[float, np.ndarray]] = []
    for payload in dicom_bytes_list:
        dataset = pydicom.dcmread(io.BytesIO(payload), force=True)
        if not hasattr(dataset, "pixel_array"):
            continue
        array = dataset.pixel_array.astype(np.float32)
        slope = float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
        array = array * slope + intercept
        key = _dicom_sort_key(dataset)
        slices.append((key, array))

    if not slices:
        raise ValueError("No DICOM slices with pixel data found.")

    slices.sort(key=lambda item: item[0])
    stacked = np.stack([item[1] for item in slices], axis=2)
    return stacked


def _dicom_sort_key(dataset) -> float:
    instance = getattr(dataset, "InstanceNumber", None)
    if instance is not None:
        try:
            return float(instance)
        except ValueError:
            pass
    position = getattr(dataset, "ImagePositionPatient", None)
    if position and isinstance(position, (list, tuple)) and len(position) >= 3:
        try:
            return float(position[2])
        except ValueError:
            pass
    location = getattr(dataset, "SliceLocation", None)
    if location is not None:
        try:
            return float(location)
        except ValueError:
            pass
    return 0.0


def _prepare_slice_image(image: Image.Image, tile_size: int) -> Image.Image:
    image = ImageOps.autocontrast(image)
    return ImageOps.fit(image, (tile_size, tile_size), method=Image.BICUBIC)


def _normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float32)
    if arr.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    if np.isnan(arr).any():
        arr = np.nan_to_num(arr)
    lo, hi = _percentile_window(arr)
    if hi <= lo:
        lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    arr = np.clip(arr, lo, hi)
    arr = (arr - lo) / (hi - lo)
    return (arr * 255).astype(np.uint8)


def _percentile_window(array: np.ndarray) -> tuple[float, float]:
    try:
        lo = float(np.percentile(array, 1))
        hi = float(np.percentile(array, 99))
        return lo, hi
    except Exception:
        return float(array.min()), float(array.max())
