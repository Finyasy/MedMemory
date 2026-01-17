import { useCallback, useRef, useState } from 'react';

type ToastType = 'success' | 'error' | 'info';

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

const useToast = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const pushToast = useCallback((type: ToastType, message: string) => {
    counterRef.current += 1;
    const id = `${Date.now()}-${counterRef.current}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return { toasts, pushToast, removeToast };
};

export default useToast;
