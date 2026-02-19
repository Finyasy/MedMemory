import { useCallback, useState } from 'react';
import { api } from '../api';
import type { BatchIngestionRequest } from '../api/generated';

type UseIngestionOptions = {
  onError: (label: string, error: unknown) => void;
  onSuccess?: (message: string) => void;
};

const defaultPayload = `{
  "labs": [
    {
      "patient_id": 1,
      "test_name": "LDL Cholesterol",
      "value": "114",
      "unit": "mg/dL",
      "reference_range": "< 100",
      "collected_at": "2025-06-02T08:30:00"
    }
  ],
  "medications": [
    {
      "patient_id": 1,
      "name": "Crestor",
      "dosage": "10mg",
      "frequency": "daily",
      "start_date": "2024-09-01"
    }
  ],
  "encounters": [
    {
      "patient_id": 1,
      "encounter_type": "office_visit",
      "encounter_date": "2025-06-02T10:00:00",
      "chief_complaint": "Annual physical"
    }
  ]
}`;

const useIngestion = ({ onError, onSuccess }: UseIngestionOptions) => {
  const [payload, setPayload] = useState(defaultPayload);
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const ingest = useCallback(async () => {
    try {
      const parsed = JSON.parse(payload) as BatchIngestionRequest;
      setIsLoading(true);
      setStatus('Ingestion running...');
      await api.ingestBatch(parsed);
      setStatus('Ingestion complete.');
      onSuccess?.('Batch ingestion completed.');
    } catch (error) {
      onError('Ingestion failed', error);
      setStatus('Invalid JSON or ingestion failed.');
    } finally {
      setIsLoading(false);
    }
  }, [payload, onError, onSuccess]);

  return { payload, setPayload, status, isLoading, ingest };
};

export default useIngestion;
