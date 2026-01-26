import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type { DocumentItem } from '../types';

type UsePatientDocumentsOptions = {
  patientId: number;
  isAuthenticated: boolean;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
};

const usePatientDocuments = ({ patientId, isAuthenticated, onError, onSuccess }: UsePatientDocumentsOptions) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const reloadDocuments = useCallback(async () => {
    if (!isAuthenticated) return;
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
  }, [patientId, isAuthenticated, onError, onSuccess]);

  useEffect(() => {
    if (!patientId || !isAuthenticated) return;
    reloadDocuments();
  }, [patientId, isAuthenticated, reloadDocuments]);

  return { documents, isLoading, reloadDocuments };
};

export default usePatientDocuments;
