import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';

type LoginModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToSignup: () => void;
  onForgotPassword: () => void;
};

const LoginModal = ({ isOpen, onClose, onSwitchToSignup, onForgotPassword }: LoginModalProps) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setTokens = useAppStore((state) => state.setTokens);
  const setUser = useAppStore((state) => state.setUser);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.login(email, password);
      setTokens(response.access_token, response.refresh_token, response.expires_in);
      
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
      <div
        className="modal-content auth-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Log in"
      >
        <aside className="auth-aside">
          <div className="auth-brand">
            <span className="auth-brand-dot" />
            <span>MedMemory</span>
          </div>
          <h3>Your medical memory, grounded and private.</h3>
          <p>
            See trends across labs, medications, and visits in one calm workspace.
          </p>
          <div className="auth-section">
            <div className="auth-section-header">
              <span className="auth-section-title">Highlights</span>
              <span className="auth-section-tag">Metabolic</span>
            </div>
            <div className="auth-highlight-grid">
              <div className="auth-highlight-card">
                <span>LDL Cholesterol</span>
                <strong>167 mg/dL</strong>
                <em>Jun 2025 - down</em>
              </div>
              <div className="auth-highlight-card">
                <span>Omega-3</span>
                <strong>4.5%</strong>
                <em>Jun 2025 - down</em>
              </div>
              <div className="auth-highlight-card">
                <span>Vitamin D</span>
                <strong>26 ng/mL</strong>
                <em>Jun 2025 - down</em>
              </div>
              <div className="auth-highlight-card">
                <span>Hemoglobin A1C</span>
                <strong>5.4%</strong>
                <em>Jun 2025 - flat</em>
              </div>
            </div>
          </div>
          <div className="auth-section">
            <span className="auth-section-title">Patient Memory Chat</span>
            <p>Ask questions, upload reports, and get grounded answers.</p>
          </div>
          <div className="auth-section">
            <span className="auth-section-title">Data intake</span>
            <div className="auth-pill-row">
              <span>Labs + meds</span>
              <span>Medications</span>
              <span>Visits</span>
            </div>
          </div>
        </aside>
        <div className="auth-form-panel">
          <div className="auth-form-header">
            <div>
              <p className="auth-eyebrow">Welcome back</p>
              <h2>Log In</h2>
              <p className="auth-subtitle">Continue to your patient workspace.</p>
            </div>
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
                data-testid="login-email"
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
              data-testid="login-password"
            />
            <button type="button" className="link-button subtle" onClick={onForgotPassword}>
              Forgot password?
            </button>
          </div>
            <button className="primary-button" type="submit" disabled={loading} data-testid="login-submit">
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
    </div>
  );
};

export default LoginModal;
