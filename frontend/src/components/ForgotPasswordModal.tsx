import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';

type ForgotPasswordModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToReset: () => void;
};

const ForgotPasswordModal = ({ isOpen, onClose, onSwitchToReset }: ForgotPasswordModalProps) => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.forgotPassword(email);
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
          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="error-message">{error}</div>}
            <div className="form-group">
              <label htmlFor="forgot-email">Email</label>
              <input
                id="forgot-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                disabled={loading}
                autoComplete="email"
                placeholder="you@example.com"
              />
            </div>
            <button className="primary-button" type="submit" disabled={loading}>
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
