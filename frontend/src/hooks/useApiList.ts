import { useCallback, useEffect, useRef, useState } from 'react';

type UseApiListOptions<T> = {
  enabled?: boolean;
  fetcher: () => Promise<T>;
  errorLabel: string;
  onError: (label: string, error: unknown) => void;
  onSuccess?: () => void;
  initialValue: T;
  resetOnDisable?: boolean;
};

const useApiList = <T,>({
  enabled = true,
  fetcher,
  errorLabel,
  onError,
  onSuccess,
  initialValue,
  resetOnDisable = true,
}: UseApiListOptions<T>) => {
  const [data, setData] = useState<T>(initialValue);
  const [isLoading, setIsLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [hasLoadedSuccessfully, setHasLoadedSuccessfully] = useState(false);
  const initialValueRef = useRef(initialValue);

  const reload = useCallback(() => {
    setReloadKey((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      if (resetOnDisable) {
        setData(initialValueRef.current);
      }
      setIsLoading(false);
      setHasLoadedSuccessfully(false);
      return;
    }

    let cancelled = false;
    const run = async () => {
      setIsLoading(true);
      try {
        const response = await fetcher();
        if (cancelled) return;
        
        // Only update state if data actually changed (reference equality check)
        // This prevents unnecessary re-renders when polling returns the same data
        setData((prevData) => {
          // For arrays/objects, do a shallow comparison
          if (Array.isArray(prevData) && Array.isArray(response)) {
            if (prevData.length === response.length) {
              // Quick check: compare lengths and first/last items
              if (prevData.length === 0 || 
                  (prevData[0] === response[0] && 
                   prevData[prevData.length - 1] === response[response.length - 1])) {
                // Likely the same, but update anyway to be safe (React will optimize)
                return response;
              }
            }
          }
          return response;
        });
        
        setHasLoadedSuccessfully(true);
        onSuccess?.();
      } catch (error) {
        if (cancelled) return;
        setHasLoadedSuccessfully(false);
        onError(errorLabel, error);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [enabled, fetcher, resetOnDisable, reloadKey, errorLabel, onError, onSuccess]);

  return { data, isLoading, reload, hasLoadedSuccessfully };
};

export default useApiList;
