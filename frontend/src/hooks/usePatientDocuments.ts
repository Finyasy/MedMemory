import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type { DocumentItem } from '../types';

type UsePatientDocumentsOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
};

const usePatientDocuments = ({ patientId, onError, onSuccess }: UsePatientDocumentsOptions) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const reloadDocuments = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.listDocuments(patientId);
      setDocuments(data);
      onSuccess?.();
    } catch (error) {
      onError('Failed to load documents', error);
    } finally {
      setIsLoading(false);
    }
  }, [patientId, onError]);

  useEffect(() => {
    if (!patientId) return;
    reloadDocuments();
  }, [patientId, reloadDocuments]);

  return { documents, isLoading, reloadDocuments };
};

export default usePatientDocuments;
