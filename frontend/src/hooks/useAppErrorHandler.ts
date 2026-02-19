import { useCallback } from 'react';
import { getUserFriendlyMessage } from '../api';

type UseAppErrorHandlerOptions = {
  setBanner: (value: string | null) => void;
  pushToast: (type: 'error' | 'info' | 'success', message: string) => void;
};

const useAppErrorHandler = ({ setBanner, pushToast }: UseAppErrorHandlerOptions) => {
  const handleError = useCallback(
    (label: string, error: unknown) => {
      const message = getUserFriendlyMessage(error);
      setBanner(`${label}: ${message}`);
      pushToast('error', `${label}. ${message}`);
    },
    [setBanner, pushToast],
  );

  const clearBanner = useCallback(() => {
    setBanner(null);
  }, [setBanner]);

  return { handleError, clearBanner };
};

export default useAppErrorHandler;

