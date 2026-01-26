import { describe, expect, it } from 'vitest';
import { getChatUploadKind, isCxrFilename } from '../uploadRouting';

const makeFile = (name: string, type: string) => new File(['x'], name, { type });

describe('getChatUploadKind', () => {
  it('detects nifti volumes', () => {
    expect(getChatUploadKind(makeFile('scan.nii', 'application/octet-stream'))).toBe('volume');
    expect(getChatUploadKind(makeFile('scan.nii.gz', 'application/gzip'))).toBe('volume');
  });

  it('detects zip volumes', () => {
    expect(getChatUploadKind(makeFile('series.zip', 'application/zip'))).toBe('volume');
  });

  it('detects wsi zips', () => {
    expect(getChatUploadKind(makeFile('wsi_patches.zip', 'application/zip'))).toBe('wsi');
  });

  it('does not classify other zips as wsi', () => {
    expect(getChatUploadKind(makeFile('volume_series.zip', 'application/zip'))).toBe('volume');
  });

  it('detects CXR filenames', () => {
    expect(isCxrFilename('patient_cxr_2024.png')).toBe(true);
    expect(isCxrFilename('chest_xray.png')).toBe(true);
    expect(isCxrFilename('scan.png')).toBe(false);
  });

  it('detects dicom singles', () => {
    expect(getChatUploadKind(makeFile('slice.dcm', 'application/dicom'))).toBe('dicom');
  });

  it('detects images', () => {
    expect(getChatUploadKind(makeFile('xray.png', 'image/png'))).toBe('image');
  });

  it('falls back to document', () => {
    expect(getChatUploadKind(makeFile('report.pdf', 'application/pdf'))).toBe('document');
  });
});
