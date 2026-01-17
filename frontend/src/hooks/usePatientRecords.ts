import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type { MedicalRecord } from '../types';

type UsePatientRecordsOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
};

const usePatientRecords = ({ patientId, onError, onSuccess }: UsePatientRecordsOptions) => {
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const reloadRecords = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getRecords(patientId);
      setRecords(data);
      onSuccess?.();
    } catch (error) {
      onError('Failed to load records', error);
    } finally {
      setIsLoading(false);
    }
  }, [patientId, onError]);

  useEffect(() => {
    if (!patientId) return;
    reloadRecords();
  }, [patientId, reloadRecords]);

  return { records, isLoading, reloadRecords };
};

export default usePatientRecords;
