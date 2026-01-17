import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type { MemorySearchResult } from '../types';

type UseMemorySearchOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  onInfo?: (message: string) => void;
};

const useMemorySearch = ({ patientId, onError, onInfo }: UseMemorySearchOptions) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MemorySearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setResults([]);
  }, [patientId]);

  const search = useCallback(async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    try {
      const response = await api.memorySearch(patientId, query.trim());
      setResults(response.results);
      onInfo?.(`Found ${response.results.length} matching chunks.`);
    } catch (error) {
      onError('Search failed', error);
    } finally {
      setIsLoading(false);
    }
  }, [patientId, query, onError, onInfo]);

  return { query, setQuery, results, isLoading, search };
};

export default useMemorySearch;
