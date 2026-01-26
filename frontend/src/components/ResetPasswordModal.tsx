import { useEffect, useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';

type ResetPasswordModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onBackToLogin?: () => void;
  initialToken?: string;
};

const ResetPasswordModal = ({ isOpen, onClose, onBackToLogin, initialToken }: ResetPasswordModalProps) => {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialToken && !token) {
      setToken(initialToken);
    }
  }, [initialToken, token]);

  useEffect(() => {
    if (isOpen && typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      if (url.pathname === '/reset-password') {
        window.history.replaceState({}, '', '/');
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleClose = () => {
    setToken('');
    setPassword('');
    setConfirmPassword('');
    setSuccess(false);
    setError('');
    onClose();
  };

  const handleBackToLogin = () => {
    handleClose();
    onBackToLogin?.();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setError(getUserFriendlyMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="modal-overlay" onClick={handleClose}>
        <div className="modal-content auth-modal" onClick={(event) => event.stopPropagation()}>
          <div className="auth-form-panel">
            <div className="auth-form-header">
              <div>
                <p className="auth-eyebrow">Success</p>
                <h2>Password updated</h2>
                <p className="auth-subtitle">Your password has been changed. You can now log in with your new password.</p>
              </div>
              <button className="modal-close" type="button" onClick={handleClose} aria-label="Close">
                ×
              </button>
            </div>
            <div className="auth-form">
              <button
                className="primary-button"
                type="button"
                onClick={handleBackToLogin}
                style={{ width: '100%' }}
              >
                Back to login
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content auth-modal" onClick={(event) => event.stopPropagation()}>
        <div className="auth-form-panel">
          <div className="auth-form-header">
            <div>
              <p className="auth-eyebrow">Almost there</p>
              <h2>Set a new password</h2>
              <p className="auth-subtitle">
                {initialToken ? 'Choose a new password for your account.' : 'Enter your reset token and new password.'}
              </p>
            </div>
            <button className="modal-close" type="button" onClick={handleClose} aria-label="Close">
              ×
            </button>
          </div>
          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="error-message">{error}</div>}
            {!initialToken && (
              <div className="form-group">
                <label htmlFor="reset-token">Reset token</label>
                <input
                  id="reset-token"
                  type="text"
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  required
                  disabled={loading}
                  autoComplete="one-time-code"
                  placeholder="Paste from email"
                />
              </div>
            )}
            <div className="form-group">
              <label htmlFor="reset-password">New password</label>
              <input
                id="reset-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
                disabled={loading}
                autoComplete="new-password"
                placeholder="At least 8 characters"
              />
            </div>
            <div className="form-group">
              <label htmlFor="reset-confirm">Confirm password</label>
              <input
                id="reset-confirm"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
                minLength={8}
                disabled={loading}
                autoComplete="new-password"
                placeholder="Re-enter password"
              />
            </div>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? 'Updating...' : 'Update password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordModal;
