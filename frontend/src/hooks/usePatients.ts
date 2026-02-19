import { useCallback } from 'react';
import useApiList from './useApiList';
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
  const fetchPatients = useCallback(() => {
    const searchTerm = debouncedSearch.trim();
    return api.listPatients(searchTerm || undefined);
  }, [debouncedSearch]);

  const { data, isLoading, reload, hasLoadedSuccessfully } = useApiList<PatientSummary[]>({
    enabled: isAuthenticated,
    fetcher: fetchPatients,
    errorLabel: 'Failed to load patients',
    onError,
    initialValue: [],
  });

  return { patients: data, isLoading, reload, hasLoadedSuccessfully };
};

export default usePatients;
