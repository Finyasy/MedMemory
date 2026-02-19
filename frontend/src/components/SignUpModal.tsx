import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';

type BackendStatus = 'checking' | 'online' | 'offline';

type SignUpModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToLogin: () => void;
  backendStatus?: BackendStatus;
};

const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

const SignUpModal = ({
  isOpen,
  onClose,
  onSwitchToLogin,
  backendStatus = 'checking',
}: SignUpModalProps) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setTokens = useAppStore((state) => state.setTokens);
  const setUser = useAppStore((state) => state.setUser);
  const backendAuthReady = backendStatus === 'online';
  const emailIsValid = isValidEmail(email.trim());
  const fullNameValid = fullName.trim().length >= 2;
  const passwordValid = password.length >= 8;
  const passwordMatch = password === confirmPassword && confirmPassword.length > 0;
  const signupFormValid = fullNameValid && emailIsValid && passwordValid && passwordMatch && backendAuthReady;
  const backendOfflineMessage = 'Backend is currently unavailable. Authentication is temporarily disabled.';
  const backendCheckingMessage = 'Checking backend connectivity. Authentication will be enabled once the service responds.';

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!signupFormValid) {
      setError(
        backendStatus === 'offline'
          ? backendOfflineMessage
          : backendStatus === 'checking'
            ? backendCheckingMessage
            : !fullNameValid
              ? 'Enter your full name.'
              : !emailIsValid
                ? 'Enter a valid email address.'
                : !passwordValid
                  ? 'Password must be at least 8 characters long.'
                  : 'Passwords do not match.',
      );
      return;
    }

    setLoading(true);

    try {
      const response = await api.signup(email.trim(), password, fullName.trim());
      setTokens(response.access_token, response.refresh_token, response.expires_in);
      
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
      <div
        className="modal-content auth-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Sign up"
      >
        <aside className="auth-aside">
          <div className="auth-brand">
            <span className="auth-brand-dot" />
            <span>MedMemory</span>
          </div>
          <h3>Build a living record of care.</h3>
          <p>
            Securely connect labs, medications, and visits to generate clear summaries.
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
              <p className="auth-eyebrow">Get started</p>
              <h2>Sign Up</h2>
              <p className="auth-subtitle">Create your workspace in under a minute.</p>
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
              Account creation will be enabled automatically once backend connectivity is confirmed.
            </p>
          )}
          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="error-message" role="alert">{error}</div>}
            <div className="form-group">
              <label htmlFor="signup-name">Full Name</label>
              <input
                id="signup-name"
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  setError('');
                }}
                required
                disabled={loading}
                autoComplete="name"
                aria-invalid={fullName.length > 0 && !fullNameValid}
              />
            </div>
            <div className="form-group">
              <label htmlFor="signup-email">Email</label>
              <input
                id="signup-email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError('');
                }}
                required
                disabled={loading}
                autoComplete="email"
                aria-invalid={email.length > 0 && !emailIsValid}
              />
            </div>
            <div className="form-group">
              <label htmlFor="signup-password">Password</label>
              <span className="auth-password-field">
                <input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError('');
                  }}
                  required
                  minLength={8}
                  disabled={loading}
                  autoComplete="new-password"
                  aria-invalid={password.length > 0 && !passwordValid}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((show) => !show)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  disabled={loading}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </span>
              <small>Must be at least 8 characters</small>
            </div>
            <div className="form-group">
              <label htmlFor="signup-confirm">Confirm Password</label>
              <span className="auth-password-field">
                <input
                  id="signup-confirm"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    setError('');
                  }}
                  required
                  disabled={loading}
                  autoComplete="new-password"
                  aria-invalid={confirmPassword.length > 0 && !passwordMatch}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowConfirmPassword((show) => !show)}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showConfirmPassword}
                  disabled={loading}
                >
                  {showConfirmPassword ? 'Hide' : 'Show'}
                </button>
              </span>
            </div>
            <button className="primary-button" type="submit" disabled={loading || !signupFormValid}>
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
    </div>
  );
};

export default SignUpModal;
