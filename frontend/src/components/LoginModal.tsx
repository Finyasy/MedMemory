import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';

type LoginModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToSignup: () => void;
};

const LoginModal = ({ isOpen, onClose, onSwitchToSignup }: LoginModalProps) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setAccessToken = useAppStore((state) => state.setAccessToken);
  const setUser = useAppStore((state) => state.setUser);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.login(email, password);
      setAccessToken(response.access_token);
      
      // Fetch user info
      const user = await api.getCurrentUser();
      setUser(user);
      
      onClose();
      setEmail('');
      setPassword('');
    } catch (err) {
      setError(getUserFriendlyMessage(err) || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Log In</h2>
          <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}
          <div className="form-group">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              autoComplete="current-password"
            />
          </div>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Log In'}
          </button>
          <p className="auth-switch">
            Don't have an account?{' '}
            <button type="button" className="link-button" onClick={onSwitchToSignup}>
              Sign Up
            </button>
          </p>
        </form>
      </div>
    </div>
  );
};

export default LoginModal;
