import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';

type BackendStatus = 'checking' | 'online' | 'offline';

type ForgotPasswordModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToReset: () => void;
  backendStatus?: BackendStatus;
};

const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

const ForgotPasswordModal = ({
  isOpen,
  onClose,
  onSwitchToReset,
  backendStatus = 'checking',
}: ForgotPasswordModalProps) => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const backendAuthReady = backendStatus === 'online';
  const emailIsValid = isValidEmail(email.trim());
  const backendOfflineMessage = 'Backend is currently unavailable. Authentication is temporarily disabled.';
  const backendCheckingMessage = 'Checking backend connectivity. Authentication will be enabled once the service responds.';

  if (!isOpen) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!emailIsValid) {
      setError('Enter the account email to receive a reset link.');
      return;
    }
    if (!backendAuthReady) {
      setError(backendStatus === 'offline' ? backendOfflineMessage : backendCheckingMessage);
      return;
    }
    setLoading(true);

    try {
      await api.forgotPassword(email.trim());
      setSubmitted(true);
    } catch (err) {
      setError(getUserFriendlyMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content auth-modal" onClick={(event) => event.stopPropagation()}>
          <div className="auth-form-panel">
            <div className="auth-form-header">
              <div>
                <p className="auth-eyebrow">Check your inbox</p>
                <h2>Reset link sent</h2>
                <p className="auth-subtitle">
                  We sent an email to <strong>{email}</strong> with instructions to reset your password.
                </p>
              </div>
              <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
                ×
              </button>
            </div>
            <div className="auth-form">
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
                Didn't receive the email? Check your spam folder or try again.
              </p>
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setSubmitted(false);
                  setEmail('');
                }}
                style={{ width: '100%', marginBottom: '0.5rem' }}
              >
                Try a different email
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={onSwitchToReset}
                style={{ width: '100%' }}
              >
                I have a reset token
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content auth-modal" onClick={(event) => event.stopPropagation()}>
          <div className="auth-form-panel">
            <div className="auth-form-header">
              <div>
                <p className="auth-eyebrow">Account recovery</p>
              <h2>Forgot your password?</h2>
              <p className="auth-subtitle">Enter your email and we'll send you a reset link.</p>
            </div>
            <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
          <div
            className={`auth-status-banner ${backendStatus === 'offline' ? 'offline' : backendStatus === 'online' ? 'online' : 'checking'}`}
            role="status"
            aria-live="polite"
          >
            {backendStatus === 'offline'
              ? backendOfflineMessage
              : backendStatus === 'online'
                ? 'Backend connected. Authentication is available.'
                : 'Checking backend connectivity...'}
          </div>
          {backendStatus === 'checking' && (
            <p className="auth-inline-hint" role="status" aria-live="polite">
              Reset link requests will be enabled automatically once backend connectivity is confirmed.
            </p>
          )}
          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="error-message" role="alert">{error}</div>}
            <div className="form-group">
              <label htmlFor="forgot-email">Email</label>
              <input
                id="forgot-email"
                type="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setError('');
                }}
                required
                disabled={loading}
                autoComplete="email"
                placeholder="you@example.com"
                aria-invalid={email.length > 0 && !emailIsValid}
              />
            </div>
            <button className="primary-button" type="submit" disabled={loading || !emailIsValid || !backendAuthReady}>
              {loading ? 'Sending...' : 'Send reset link'}
            </button>
            <p className="auth-switch">
              Remember your password?{' '}
              <button type="button" className="link-button" onClick={onClose}>
                Back to login
              </button>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordModal;
