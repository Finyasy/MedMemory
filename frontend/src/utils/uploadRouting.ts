export type ChatUploadKind = 'volume' | 'image' | 'document' | 'dicom' | 'wsi';

export const getChatUploadKind = (file: File): ChatUploadKind => {
  const name = file.name.toLowerCase();
  const isNifti = name.endsWith('.nii') || name.endsWith('.nii.gz');
  const isZip = name.endsWith('.zip') || file.type === 'application/zip';
  const isDicom = name.endsWith('.dcm');
  const isWsiZip = isZip && /(wsi|patch)/.test(name);

  if (isDicom) {
    return 'dicom';
  }
  if (isWsiZip) {
    return 'wsi';
  }
  if (isNifti || isZip) {
    return 'volume';
  }
  if (file.type.startsWith('image/')) {
    return 'image';
  }
  return 'document';
};

export const isCxrFilename = (name: string): boolean => {
  const lower = name.toLowerCase();
  return /(cxr|xray|chest)/.test(lower);
};
