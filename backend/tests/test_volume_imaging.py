from __future__ import annotations

import io
import tempfile

import nibabel as nib
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from app.services.imaging.volume import (
    build_volume_montage_from_array,
    load_dicom_volume,
    load_nifti_volume,
)


def _dicom_bytes(instance: int, value: int) -> bytes:
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = f"1.2.3.4.{instance}"
    ds.Modality = "CT"
    ds.Rows = 4
    ds.Columns = 4
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.InstanceNumber = instance
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 0

    pixel = np.full((4, 4), value, dtype=np.int16)
    ds.PixelData = pixel.tobytes()

    buffer = io.BytesIO()
    pydicom.dcmwrite(buffer, ds, little_endian=True, implicit_vr=False)
    return buffer.getvalue()


def test_load_nifti_volume():
    volume = np.random.rand(8, 8, 5).astype(np.float32)
    image = nib.Nifti1Image(volume, affine=np.eye(4))
    with tempfile.NamedTemporaryFile(suffix=".nii.gz") as tmp:
        nib.save(image, tmp.name)
        tmp.seek(0)
        payload = tmp.read()

    loaded = load_nifti_volume(payload)
    assert loaded.shape == (8, 8, 5)


def test_load_dicom_volume_sorts_by_instance():
    payloads = [
        _dicom_bytes(2, 20),
        _dicom_bytes(1, 10),
        _dicom_bytes(3, 30),
    ]
    volume = load_dicom_volume(payloads)
    assert volume.shape == (4, 4, 3)
    assert int(volume[0, 0, 0]) == 10
    assert int(volume[0, 0, 1]) == 20
    assert int(volume[0, 0, 2]) == 30


def test_build_volume_montage_from_array():
    volume = np.linspace(0, 1, 4 * 4 * 6, dtype=np.float32).reshape((4, 4, 6))
    result = build_volume_montage_from_array(volume, sample_count=4, tile_size=64)
    assert result.total_slices == 6
    assert len(result.sampled_indices) == 4
    assert result.montage_bytes
