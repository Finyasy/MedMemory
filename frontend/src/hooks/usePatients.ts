import { useEffect, useState } from 'react';
import { api } from '../api';
import useDebouncedValue from './useDebouncedValue';
import type { PatientSummary } from '../types';

type UsePatientsOptions = {
  search: string;
  onError: (label: string, error: unknown) => void;
};

const usePatients = ({ search, onError }: UsePatientsOptions) => {
  const debouncedSearch = useDebouncedValue(search, 300);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchPatients = async () => {
      if (!debouncedSearch.trim()) {
        setPatients([]);
        return;
      }
      setIsLoading(true);
      try {
        const data = await api.listPatients(debouncedSearch.trim());
        setPatients(data);
      } catch (error) {
        onError('Failed to load patients', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPatients();
  }, [debouncedSearch, onError]);

  return { patients, isLoading };
};

export default usePatients;
