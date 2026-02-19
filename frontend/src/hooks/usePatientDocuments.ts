import { useCallback } from 'react';
import useApiList from './useApiList';
import { api } from '../api';
import type { DocumentItem } from '../types';

type UsePatientDocumentsOptions = {
  patientId: number;
  isAuthenticated: boolean;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
};

const usePatientDocuments = ({ patientId, isAuthenticated, onError, onSuccess }: UsePatientDocumentsOptions) => {
  const fetchDocuments = useCallback(() => api.listDocuments(patientId), [patientId]);

  const { data, isLoading, reload } = useApiList<DocumentItem[]>({
    enabled: Boolean(patientId) && isAuthenticated,
    fetcher: fetchDocuments,
    errorLabel: 'Failed to load documents',
    onError,
    onSuccess,
    initialValue: [],
  });

  return { documents: data, isLoading, reloadDocuments: reload };
};

export default usePatientDocuments;
