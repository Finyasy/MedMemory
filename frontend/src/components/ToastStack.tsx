import type { Toast } from '../hooks/useToast';

type ToastStackProps = {
  toasts: Toast[];
};

const ToastStack = ({ toasts }: ToastStackProps) => {
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      ))}
    </div>
  );
};

export default ToastStack;
