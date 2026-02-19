import { useCallback } from 'react';
import useApiList from './useApiList';
import { api } from '../api';
import type { MedicalRecord } from '../types';

type UsePatientRecordsOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
};

const usePatientRecords = ({ patientId, onError, onSuccess }: UsePatientRecordsOptions) => {
  const fetchRecords = useCallback(() => api.getRecords(patientId), [patientId]);

  const { data, isLoading, reload } = useApiList<MedicalRecord[]>({
    enabled: Boolean(patientId),
    fetcher: fetchRecords,
    errorLabel: 'Failed to load records',
    onError,
    onSuccess,
    initialValue: [],
  });

  return { records: data, isLoading, reloadRecords: reload };
};

export default usePatientRecords;
