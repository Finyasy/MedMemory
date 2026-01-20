import { useEffect, useState } from 'react';
import { api } from '../api';
import useDebouncedValue from './useDebouncedValue';
import type { PatientSummary } from '../types';

type UsePatientsOptions = {
  search: string;
  isAuthenticated: boolean;
  onError: (label: string, error: unknown) => void;
};

const usePatients = ({ search, isAuthenticated, onError }: UsePatientsOptions) => {
  const debouncedSearch = useDebouncedValue(search, 300);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchPatients = async () => {
      if (!isAuthenticated) {
        setPatients([]);
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const searchTerm = debouncedSearch.trim();
        const data = await api.listPatients(searchTerm || undefined);
        setPatients(data);
      } catch (error) {
        onError('Failed to load patients', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPatients();
  }, [debouncedSearch, isAuthenticated, onError]);

  return { patients, isLoading };
};

export default usePatients;
