import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';

type SignUpModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToLogin: () => void;
};

const SignUpModal = ({ isOpen, onClose, onSwitchToLogin }: SignUpModalProps) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setAccessToken = useAppStore((state) => state.setAccessToken);
  const setUser = useAppStore((state) => state.setUser);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const response = await api.signup(email, password, fullName);
      setAccessToken(response.access_token);
      
      // Fetch user info
      const user = await api.getCurrentUser();
      setUser(user);
      
      onClose();
      setFullName('');
      setEmail('');
      setPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(getUserFriendlyMessage(err) || 'Sign up failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Sign Up</h2>
          <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}
          <div className="form-group">
            <label htmlFor="signup-name">Full Name</label>
            <input
              id="signup-name"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              disabled={loading}
              autoComplete="name"
            />
          </div>
          <div className="form-group">
            <label htmlFor="signup-email">Email</label>
            <input
              id="signup-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label htmlFor="signup-password">Password</label>
            <input
              id="signup-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              disabled={loading}
              autoComplete="new-password"
            />
            <small>Must be at least 8 characters</small>
          </div>
          <div className="form-group">
            <label htmlFor="signup-confirm">Confirm Password</label>
            <input
              id="signup-confirm"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={loading}
              autoComplete="new-password"
            />
          </div>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Sign Up'}
          </button>
          <p className="auth-switch">
            Already have an account?{' '}
            <button type="button" className="link-button" onClick={onSwitchToLogin}>
              Log In
            </button>
          </p>
        </form>
      </div>
    </div>
  );
};

export default SignUpModal;
