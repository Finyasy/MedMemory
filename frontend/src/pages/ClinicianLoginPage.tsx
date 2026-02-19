import { useState } from 'react';
import { api, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';

type Tab = 'login' | 'signup';

export default function ClinicianLoginPage() {
  const [tab, setTab] = useState<Tab>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [registrationNumber, setRegistrationNumber] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const setTokens = useAppStore((state) => state.setTokens);
  const setUser = useAppStore((state) => state.setUser);
  const setClinician = useAppStore((state) => state.setClinician);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.clinicianLogin(email, password);
      setTokens(res.access_token, res.refresh_token, res.expires_in);
      setClinician(true);
      const profile = await api.getClinicianProfile();
      setUser({
        id: profile.user_id,
        email: profile.email,
        full_name: profile.full_name,
        is_active: true,
      });
    } catch (err) {
      setError(getUserFriendlyMessage(err) || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.clinicianSignup({
        email,
        password,
        full_name: fullName,
        registration_number: registrationNumber.trim(),
      });
      setTokens(res.access_token, res.refresh_token, res.expires_in);
      setClinician(true);
      setUser({
        id: res.user_id,
        email: res.email,
        full_name: fullName,
        is_active: true,
      });
    } catch (err) {
      setError(getUserFriendlyMessage(err) || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="clinician-login-page">
      <div className="clinician-login-card">
        <div className="clinician-login-header">
          <h1>Clinician Portal</h1>
          <p>Sign in to review patient uploads and use technical chat.</p>
        </div>
        <div className="clinician-tabs">
          <button
            type="button"
            className={tab === 'login' ? 'active' : ''}
            onClick={() => { setTab('login'); setError(''); }}
          >
            Log in
          </button>
          <button
            type="button"
            className={tab === 'signup' ? 'active' : ''}
            onClick={() => { setTab('signup'); setError(''); }}
          >
            Sign up
          </button>
        </div>
        {error && <div className="clinician-error" role="alert">{error}</div>}
        {tab === 'login' && (
          <form onSubmit={handleLogin} className="clinician-form">
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        )}
        {tab === 'signup' && (
          <form onSubmit={handleSignup} className="clinician-form">
            <label>
              Full name
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                autoComplete="name"
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Password (min 8 characters)
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </label>
            <label>
              Registration Number
              <input
                type="text"
                value={registrationNumber}
                onChange={(e) => setRegistrationNumber(e.target.value)}
                placeholder="Professional registration number"
                required
              />
            </label>
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        )}
        <p className="clinician-back">
          <a href="/">← Back to MedMemory</a>
        </p>
      </div>
    </div>
  );
}
