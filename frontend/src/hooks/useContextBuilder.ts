import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type UseContextBuilderOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  onSuccess?: (message: string) => void;
};

const useContextBuilder = ({ patientId, onError, onSuccess }: UseContextBuilderOptions) => {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setResult('');
  }, [patientId]);

  const generate = useCallback(async () => {
    if (!question.trim()) return;
    setIsLoading(true);
    try {
      const response = await api.getContext(patientId, question.trim());
      setResult(response.context);
      onSuccess?.(`Context generated with ${response.num_sources} sources.`);
    } catch (error) {
      onError('Context generation failed', error);
    } finally {
      setIsLoading(false);
    }
  }, [patientId, question, onError, onSuccess]);

  return { question, setQuestion, result, isLoading, generate };
};

export default useContextBuilder;
