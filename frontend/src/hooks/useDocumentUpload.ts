import { useCallback } from 'react';
import { api } from '../api';
import { getExistingDocumentId } from '../utils/documents';

type UploadResult =
  | { kind: 'uploaded'; id: number }
  | { kind: 'duplicate-same'; id: number }
  | { kind: 'duplicate-other'; id: number };

const useDocumentUpload = (patientId: number) => {
  const uploadWithDuplicateCheck = useCallback(
    async (file: File, metadata: { title?: string; category?: string; document_type?: string; description?: string } = {}) => {
      try {
        const uploaded = await api.uploadDocument(patientId, file, metadata);
        return { kind: 'uploaded', id: uploaded.id } as UploadResult;
      } catch (error) {
        const existingId = getExistingDocumentId(error);
        if (!existingId) {
          throw error;
        }
        const existingDoc = await api.getDocument(existingId);
        if (existingDoc.patient_id === patientId) {
          return { kind: 'duplicate-same', id: existingId } as UploadResult;
        }
        return { kind: 'duplicate-other', id: existingId } as UploadResult;
      }
    },
    [patientId],
  );

  return { uploadWithDuplicateCheck };
};

export type { UploadResult };
export default useDocumentUpload;
