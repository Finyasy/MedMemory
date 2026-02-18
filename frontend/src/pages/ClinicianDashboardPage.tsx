import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError, getUserFriendlyMessage } from '../api';
import useAppStore from '../store/useAppStore';
import useChat from '../hooks/useChat';
import useAppErrorHandler from '../hooks/useAppErrorHandler';
import useToast from '../hooks/useToast';
import ChatInterface from '../components/ChatInterface';
import type { DocumentItem, MedicalRecord } from '../types';

type Tab = 'login' | 'signup';
type BackendStatus = 'checking' | 'online' | 'offline';
type OnboardingStepState = 'upcoming' | 'active' | 'complete' | 'ready';

type OnboardingStep = {
  key: string;
  title: string;
  detail: string;
  state: OnboardingStepState;
};
type MobileSection = 'queue' | 'link' | 'panel';

type PatientWithGrant = {
  patient_id: number;
  patient_first_name: string;
  patient_last_name: string;
  patient_full_name: string;
  grant_id: number;
  grant_status: string;
  grant_scopes: string;
  granted_at?: string | null;
  expires_at?: string | null;
};

const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
const ONBOARDING_STEP_LABEL: Record<OnboardingStepState, string> = {
  upcoming: 'Next',
  active: 'In progress',
  complete: 'Done',
  ready: 'Ready',
};

export default function ClinicianDashboardPage() {
  const accessToken = useAppStore((state) => state.accessToken);
  const setAccessToken = useAppStore((state) => state.setAccessToken);
  const setUser = useAppStore((state) => state.setUser);
  const setClinician = useAppStore((state) => state.setClinician);
  const logout = useAppStore((state) => state.logout);

  const [clinicianVerified, setClinicianVerified] = useState<boolean | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [selectedPatientName, setSelectedPatientName] = useState<string>('');

  const [tab, setTab] = useState<Tab>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [registrationNumber, setRegistrationNumber] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotMessage, setForgotMessage] = useState<string | null>(null);
  const [forgotError, setForgotError] = useState<string | null>(null);

  const [patients, setPatients] = useState<PatientWithGrant[]>([]);
  const [uploads, setUploads] = useState<DocumentItem[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [loadingUploads, setLoadingUploads] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastQueueSync, setLastQueueSync] = useState<Date | null>(null);

  const [requestPatientId, setRequestPatientId] = useState('');
  const [requestAccessLoading, setRequestAccessLoading] = useState(false);
  const [requestAccessError, setRequestAccessError] = useState<string | null>(null);
  const [patientSearchTerm, setPatientSearchTerm] = useState('');
  const [showWorkspaceChecklist, setShowWorkspaceChecklist] = useState(false);
  const [showQueueInsights, setShowQueueInsights] = useState(false);
  const [mobileSection, setMobileSection] = useState<MobileSection>('queue');

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingRecords, setLoadingRecords] = useState(false);

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const requestPatientInputRef = useRef<HTMLInputElement>(null);

  const user = useAppStore((state) => state.user);
  const { pushToast } = useToast();
  const stableNoBanner = useCallback((_value: string | null) => {}, []);
  const { handleError } = useAppErrorHandler({ setBanner: stableNoBanner, pushToast });
  const handleErrorRef = useRef(handleError);
  handleErrorRef.current = handleError;
  const emailIsValid = isValidEmail(email.trim());
  const backendAuthReady = backendStatus === 'online';
  const loginFormValid = emailIsValid && password.trim().length > 0 && backendAuthReady;
  const signupFormValid =
    emailIsValid &&
    password.length >= 8 &&
    fullName.trim().length >= 2 &&
    registrationNumber.trim().length >= 4 &&
    backendAuthReady;
  const backendOfflineMessage = 'Backend is currently unavailable. Authentication is temporarily disabled.';
  const backendCheckingMessage = 'Checking backend connectivity. Authentication will be enabled once the service responds.';

  useEffect(() => {
    let cancelled = false;
    let retryTimerId: number | undefined;
    const retryDelaysMs = [0, 1200, 3500];

    const runHealthCheck = (attempt: number) => {
      retryTimerId = window.setTimeout(async () => {
        try {
          await api.getHealth();
          if (!cancelled) setBackendStatus('online');
        } catch {
          if (cancelled) return;
          if (attempt < retryDelaysMs.length - 1) {
            runHealthCheck(attempt + 1);
            return;
          }
          setBackendStatus('offline');
        }
      }, retryDelaysMs[attempt]);
    };

    runHealthCheck(0);
    const pollTimerId = window.setInterval(() => runHealthCheck(0), 45000);
    return () => {
      cancelled = true;
      if (retryTimerId) window.clearTimeout(retryTimerId);
      window.clearInterval(pollTimerId);
    };
  }, []);

  const verifyClinician = useCallback(async () => {
    if (!accessToken) {
      setClinicianVerified(false);
      return;
    }
    try {
      const profile = await api.getClinicianProfile();
      setUser({
        id: profile.user_id,
        email: profile.email,
        full_name: profile.full_name,
        is_active: true,
      });
      setClinician(true);
      setClinicianVerified(true);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setAccessToken(null);
        setClinician(false);
      }
      setClinicianVerified(false);
    }
  }, [accessToken, setAccessToken, setUser, setClinician]);

  useEffect(() => {
    if (!accessToken) {
      setClinicianVerified(false);
      return;
    }
    verifyClinician();
  }, [accessToken, verifyClinician]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setForgotError(null);
    setForgotMessage(null);
    if (!loginFormValid) {
      setAuthError(
        backendStatus === 'offline'
          ? backendOfflineMessage
          : backendStatus === 'checking'
            ? backendCheckingMessage
            : 'Enter a valid email and password.',
      );
      return;
    }
    setAuthLoading(true);
    try {
      const res = await api.clinicianLogin(email.trim(), password);
      useAppStore.getState().setTokens(res.access_token, res.refresh_token, res.expires_in);
      setClinician(true);
      const profile = await api.getClinicianProfile();
      setUser({
        id: profile.user_id,
        email: profile.email,
        full_name: profile.full_name,
        is_active: true,
      });
    } catch (err) {
      setAuthError(getUserFriendlyMessage(err) || 'Login failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setForgotError(null);
    setForgotMessage(null);
    if (!signupFormValid) {
      setAuthError(
        backendStatus === 'offline'
          ? backendOfflineMessage
          : backendStatus === 'checking'
            ? backendCheckingMessage
          : 'Complete all fields with valid information to create a clinician account.',
      );
      return;
    }
    setAuthLoading(true);
    try {
      const res = await api.clinicianSignup({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        registration_number: registrationNumber.trim(),
      });
      useAppStore.getState().setTokens(res.access_token, res.refresh_token, res.expires_in);
      setClinician(true);
      setUser({
        id: res.user_id,
        email: res.email,
        full_name: fullName.trim(),
        is_active: true,
      });
    } catch (err) {
      setAuthError(getUserFriendlyMessage(err) || 'Signup failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleForgotPassword = useCallback(async () => {
    setForgotError(null);
    setForgotMessage(null);
    if (!emailIsValid) {
      setForgotError('Enter the account email to receive a reset link.');
      return;
    }
    if (!backendAuthReady) {
      setForgotError(backendStatus === 'offline' ? backendOfflineMessage : backendCheckingMessage);
      return;
    }
    setForgotLoading(true);
    try {
      const result = await api.forgotPassword(email.trim());
      setForgotMessage(result.message || 'If the account exists, a reset link has been sent.');
    } catch (err) {
      setForgotError(getUserFriendlyMessage(err) || 'Unable to send reset link.');
    } finally {
      setForgotLoading(false);
    }
  }, [email, emailIsValid, backendAuthReady, backendStatus, backendCheckingMessage, backendOfflineMessage]);

  const loadPatientListAndUploads = useCallback(async () => {
    setLoadError(null);
    setLoadingPatients(true);
    setLoadingUploads(true);
    try {
      // Fetch all linked patients (active + pending) so clinician can see and request access
      const [patientList, uploadList] = await Promise.all([
        api.listClinicianPatients(undefined),
        api.listClinicianUploads({ limit: 50 }),
      ]);
      setPatients(patientList);
      setUploads(uploadList);
      setLastQueueSync(new Date());
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        return;
      }
      const message = getUserFriendlyMessage(err) || 'Unable to load';
      setLoadError(message);
      handleErrorRef.current('Failed to load clinician data', err);
    } finally {
      setLoadingPatients(false);
      setLoadingUploads(false);
    }
  }, [logout]);

  const handleRequestAccess = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const patientId = parseInt(requestPatientId.trim(), 10);
    if (Number.isNaN(patientId) || patientId <= 0) {
      setRequestAccessError('Enter a valid patient ID (number).');
      return;
    }
    setRequestAccessError(null);
    setRequestAccessLoading(true);
    try {
      await api.requestPatientAccess({ patient_id: patientId });
      pushToast('success', 'Access requested. The patient must approve before you can view their records.');
      setRequestPatientId('');
      await loadPatientListAndUploads();
    } catch (err) {
      const msg = getUserFriendlyMessage(err) || 'Request failed';
      setRequestAccessError(msg);
      handleErrorRef.current('Request access failed', err);
    } finally {
      setRequestAccessLoading(false);
    }
  }, [requestPatientId, pushToast, loadPatientListAndUploads]);

  const loadPatientWorkspace = useCallback(async (patientId: number) => {
    setLoadingDocs(true);
    setLoadingRecords(true);
    try {
      const [docs, recs] = await Promise.all([
        api.listClinicianPatientDocuments(patientId),
        api.listClinicianPatientRecords(patientId),
      ]);
      setDocuments(docs);
      setRecords(recs);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setSelectedPatientId(null);
        setSelectedPatientName('');
        return;
      }
      handleErrorRef.current('Failed to load patient data', err);
    } finally {
      setLoadingDocs(false);
      setLoadingRecords(false);
    }
  }, []);

  useEffect(() => {
    if (!accessToken || clinicianVerified !== true) return;
    loadPatientListAndUploads();
  }, [accessToken, clinicianVerified, loadPatientListAndUploads]);

  useEffect(() => {
    if (selectedPatientId === null) return;
    loadPatientWorkspace(selectedPatientId);
  }, [selectedPatientId, loadPatientWorkspace]);

  useEffect(() => {
    if (!userMenuOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('click', handleClick);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('click', handleClick);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [userMenuOpen]);

  const {
    messages,
    question,
    setQuestion,
    isStreaming,
    send,
  } = useChat({
    patientId: selectedPatientId ?? 0,
    onError: handleError,
    clinicianMode: true,
  });

  const handleSelectPatient = useCallback((patientId: number, fullName: string) => {
    setSelectedPatientId(patientId);
    setSelectedPatientName(fullName);
    setShowQueueInsights(false);
    setMobileSection('panel');
  }, []);

  const handleBackToList = useCallback(() => {
    setSelectedPatientId(null);
    setSelectedPatientName('');
    setMobileSection('queue');
  }, []);

  const handleFocusLinkPatient = useCallback(() => {
    setMobileSection('link');
    requestPatientInputRef.current?.focus();
  }, []);

  const handleLogout = useCallback(() => {
    logout();
    window.location.href = '/clinician';
  }, [logout]);

  const activePatientCount = useMemo(
    () => patients.filter((p) => p.grant_status === 'active').length,
    [patients],
  );
  const pendingPatientCount = useMemo(
    () => patients.filter((p) => p.grant_status === 'pending').length,
    [patients],
  );
  const isQueueLoading = loadingPatients || loadingUploads;
  const activePatients = useMemo(
    () => patients.filter((p) => p.grant_status === 'active'),
    [patients],
  );
  const pendingPatients = useMemo(
    () => patients.filter((p) => p.grant_status === 'pending'),
    [patients],
  );
  const recentUploadsPreview = useMemo(
    () => uploads.slice(0, 4),
    [uploads],
  );
  const filteredPatients = useMemo(() => {
    const term = patientSearchTerm.trim().toLowerCase();
    if (!term) return patients;
    return patients.filter((p) =>
      p.patient_full_name.toLowerCase().includes(term)
      || String(p.patient_id).includes(term),
    );
  }, [patients, patientSearchTerm]);

  const handleSelectFirstActivePatient = useCallback(() => {
    if (activePatients.length === 0) return;
    const firstActive = activePatients[0];
    handleSelectPatient(firstActive.patient_id, firstActive.patient_full_name);
  }, [activePatients, handleSelectPatient]);

  const queueSyncLabel = useMemo(() => {
    if (isQueueLoading) return 'Refreshing queue…';
    if (!lastQueueSync) return 'Queue not synced yet';
    return `Synced ${lastQueueSync.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })}`;
  }, [isQueueLoading, lastQueueSync]);

  const onboardingSteps = useMemo<OnboardingStep[]>(() => {
    const hasRequestedOrLinked = patients.length > 0;
    return [
      {
        key: 'request',
        title: 'Request access',
        detail: hasRequestedOrLinked
          ? 'A patient link already exists in your queue.'
          : 'Enter a patient ID in the left panel to submit access.',
        state: hasRequestedOrLinked ? 'complete' : requestPatientId.trim() ? 'active' : 'upcoming',
      },
      {
        key: 'approval',
        title: 'Patient approval',
        detail: pendingPatientCount > 0
          ? 'Waiting for patient confirmation before records unlock.'
          : activePatientCount > 0
            ? 'Approved links are available now.'
            : 'No pending requests yet.',
        state: activePatientCount > 0 ? 'complete' : pendingPatientCount > 0 ? 'active' : 'upcoming',
      },
      {
        key: 'workspace',
        title: 'Open workspace',
        detail: selectedPatientId !== null
          ? `${selectedPatientName} is open for chat and chart review.`
          : activePatientCount > 0
            ? 'Open an active patient to start chart review.'
            : 'Unlock this step after approval.',
        state: selectedPatientId !== null ? 'active' : activePatientCount > 0 ? 'ready' : 'upcoming',
      },
    ];
  }, [
    patients.length,
    requestPatientId,
    pendingPatientCount,
    activePatientCount,
    selectedPatientId,
    selectedPatientName,
  ]);

  const nextStepTitle = activePatientCount > 0
    ? 'Open an approved patient'
    : pendingPatientCount > 0
      ? 'Monitor pending approvals'
      : 'Request your first patient link';
  const nextStepDescription = activePatientCount > 0
    ? 'You already have approved patients. Open one to review documents and ask chart questions.'
    : pendingPatientCount > 0
      ? 'Requests are in progress. Patients must approve access before records appear.'
      : 'No linked patients yet. Use the left panel to submit a patient ID access request.';

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  // —— Loading (verifying clinician) ——
  if (accessToken && clinicianVerified === null) {
    return (
      <div className="clinician-app clinician-loading-screen">
        <div className="loading-spinner" />
        <p>Verifying clinician access…</p>
      </div>
    );
  }

  // —— Not authenticated: login/signup on same page ——
  if (!accessToken || clinicianVerified === false) {
    return (
      <div className="clinician-portal-page clinician-login-section">
        <div className="clinician-login-card">
          <div className="clinician-login-header">
            <h1>Clinician Portal</h1>
            <p>Sign in to review patient uploads and use technical chat.</p>
          </div>
          <div className="clinician-tabs">
            <button
              type="button"
              className={tab === 'login' ? 'active' : ''}
              onClick={() => {
                setTab('login');
                setAuthError('');
                setForgotError(null);
                setForgotMessage(null);
              }}
            >
              Log in
            </button>
            <button
              type="button"
              className={tab === 'signup' ? 'active' : ''}
              onClick={() => {
                setTab('signup');
                setAuthError('');
                setForgotError(null);
                setForgotMessage(null);
              }}
            >
              Sign up
            </button>
          </div>
          <div
            className={`clinician-status-banner ${backendStatus === 'offline' ? 'offline' : backendStatus === 'online' ? 'online' : 'checking'}`}
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
            <p className="clinician-inline-hint" role="status" aria-live="polite">
              Authentication buttons will enable automatically once the backend is reachable.
            </p>
          )}
          {authError && <div className="clinician-error" role="alert">{authError}</div>}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="clinician-form">
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setAuthError('');
                    setForgotError(null);
                    setForgotMessage(null);
                  }}
                  required
                  autoComplete="email"
                  aria-invalid={email.length > 0 && !emailIsValid}
                />
              </label>
              {email.length > 0 && !emailIsValid && (
                <p className="clinician-inline-error" role="alert">
                  Enter a valid email address.
                </p>
              )}
              <label>
                Password
                <span className="clinician-password-field">
                  <input
                    type={showLoginPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setAuthError('');
                    }}
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="clinician-password-toggle"
                    onClick={() => setShowLoginPassword((show) => !show)}
                    aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showLoginPassword}
                  >
                    {showLoginPassword ? 'Hide' : 'Show'}
                  </button>
                </span>
              </label>
              <button type="submit" className="primary-button" disabled={authLoading || !loginFormValid}>
                {authLoading ? 'Signing in…' : 'Sign in'}
              </button>
              <button
                type="button"
                className="link-button subtle clinician-forgot-button"
                onClick={handleForgotPassword}
                disabled={forgotLoading || !backendAuthReady}
              >
                {forgotLoading ? 'Sending reset link...' : 'Forgot password? Send reset link'}
              </button>
              {forgotMessage && <p className="clinician-inline-success">{forgotMessage}</p>}
              {forgotError && <p className="clinician-inline-error" role="alert">{forgotError}</p>}
            </form>
          )}
          {tab === 'signup' && (
            <form onSubmit={handleSignup} className="clinician-form">
              <label>
                Full name
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    setAuthError('');
                  }}
                  required
                  autoComplete="name"
                />
              </label>
              {fullName.trim().length > 0 && fullName.trim().length < 2 && (
                <p className="clinician-inline-error" role="alert">
                  Enter your full name.
                </p>
              )}
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setAuthError('');
                  }}
                  required
                  autoComplete="email"
                  aria-invalid={email.length > 0 && !emailIsValid}
                />
              </label>
              {email.length > 0 && !emailIsValid && (
                <p className="clinician-inline-error" role="alert">
                  Enter a valid email address.
                </p>
              )}
              <label>
                Password (min 8 characters)
                <span className="clinician-password-field">
                  <input
                    type={showSignupPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setAuthError('');
                    }}
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="clinician-password-toggle"
                    onClick={() => setShowSignupPassword((show) => !show)}
                    aria-label={showSignupPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showSignupPassword}
                  >
                    {showSignupPassword ? 'Hide' : 'Show'}
                  </button>
                </span>
              </label>
              {password.length > 0 && password.length < 8 && (
                <p className="clinician-inline-error" role="alert">
                  Password must be at least 8 characters.
                </p>
              )}
              <label>
                Registration Number
                <input
                  type="text"
                  value={registrationNumber}
                  onChange={(e) => {
                    setRegistrationNumber(e.target.value);
                    setAuthError('');
                  }}
                  placeholder="Professional registration number"
                  required
                />
              </label>
              {registrationNumber.trim().length > 0 && registrationNumber.trim().length < 4 && (
                <p className="clinician-inline-error" role="alert">
                  Enter your registration number.
                </p>
              )}
              <button type="submit" className="primary-button" disabled={authLoading || !signupFormValid}>
                {authLoading ? 'Creating account…' : 'Create account'}
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

  // —— Authenticated: one page = header (no MedMemory) + left sidebar | center chat | right customer panel ——
  return (
    <div className="clinician-portal-page clinician-authenticated">
      <header className="clinician-header clinician-header-modern">
        <div className="clinician-header-inner">
          <div className="clinician-brand-block">
            <h1 className="clinician-brand">Clinician Portal</h1>
            <span
              className={`clinician-header-status ${backendStatus === 'offline' ? 'offline' : backendStatus === 'online' ? 'online' : 'checking'}`}
              role="status"
              aria-live="polite"
            >
              {backendStatus === 'offline'
                ? 'Backend offline'
                : backendStatus === 'online'
                  ? 'Backend online'
                  : 'Checking backend'}
            </span>
          </div>
          <div className="clinician-header-actions" ref={userMenuRef}>
            <button
              type="button"
              className="clinician-user-trigger"
              onClick={() => setUserMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
            >
              <span className="clinician-user-avatar" aria-hidden>
                {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
              </span>
              <span className="clinician-user-name">{user?.full_name || 'Clinician'}</span>
              <span className="clinician-user-chevron" aria-hidden>▼</span>
            </button>
            {userMenuOpen && (
              <div className="clinician-user-dropdown" role="menu">
                <div className="clinician-user-dropdown-header">
                  <span className="clinician-user-dropdown-avatar">
                    {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
                  </span>
                  <div className="clinician-user-dropdown-info">
                    <strong>{user?.full_name || 'Clinician'}</strong>
                    <span className="clinician-user-dropdown-email">{user?.email || ''}</span>
                    <span className="clinician-user-dropdown-role">Clinician</span>
                  </div>
                </div>
                <div className="clinician-user-dropdown-divider" />
                <button
                  type="button"
                  className="clinician-user-dropdown-item"
                  onClick={() => {
                    setUserMenuOpen(false);
                    handleLogout();
                  }}
                  role="menuitem"
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <section className="clinician-overview-strip" aria-label="Clinician dashboard overview">
        <article className="clinician-overview-card" data-metric="active">
          <span className="clinician-overview-label">Active links</span>
          <strong className="clinician-overview-value">{activePatientCount}</strong>
          <span className="clinician-overview-note">
            {activePatientCount === 0 ? 'No approved patients yet' : 'Ready to open workspace'}
          </span>
        </article>
        <article className="clinician-overview-card" data-metric="pending">
          <span className="clinician-overview-label">Pending approvals</span>
          <strong className="clinician-overview-value">{pendingPatientCount}</strong>
          <span className="clinician-overview-note">
            {pendingPatientCount === 0 ? 'Queue is clear' : 'Waiting on patient approval'}
          </span>
        </article>
        <article className="clinician-overview-card" data-metric="uploads">
          <span className="clinician-overview-label">Uploads</span>
          <strong className="clinician-overview-value">{uploads.length}</strong>
          <span className="clinician-overview-note">
            {uploads.length === 0 ? 'No documents received yet' : 'Recent files available'}
          </span>
        </article>
        <article className="clinician-overview-card" data-metric="current">
          <span className="clinician-overview-label">Current patient</span>
          <strong className="clinician-overview-value">
            {selectedPatientName || 'None selected'}
          </strong>
          <span className="clinician-overview-note">
            {selectedPatientId === null ? 'Select from linked patients' : `Patient ID ${selectedPatientId}`}
          </span>
        </article>
      </section>

      <section className="clinician-action-strip" aria-label="Clinician quick actions">
        <div className="clinician-action-buttons">
          <button type="button" className="ghost-button compact clinician-action-btn" onClick={handleFocusLinkPatient}>
            Link patient
          </button>
          <button
            type="button"
            className="ghost-button compact clinician-action-btn"
            onClick={loadPatientListAndUploads}
            disabled={isQueueLoading}
          >
            {isQueueLoading ? 'Refreshing…' : 'Refresh queue'}
          </button>
          <button
            type="button"
            className="primary-button clinician-action-btn"
            onClick={handleSelectFirstActivePatient}
            disabled={activePatients.length === 0}
          >
            Open first active patient
          </button>
        </div>
        <p className="clinician-sync-chip" role="status" aria-live="polite">
          {queueSyncLabel}
        </p>
      </section>
      <section className="clinician-mobile-section-switcher" aria-label="Mobile clinician sections">
        <button
          type="button"
          className={mobileSection === 'queue' ? 'active' : ''}
          onClick={() => setMobileSection('queue')}
        >
          Queue
        </button>
        <button
          type="button"
          className={mobileSection === 'link' ? 'active' : ''}
          onClick={() => setMobileSection('link')}
        >
          Link
        </button>
        <button
          type="button"
          className={mobileSection === 'panel' ? 'active' : ''}
          onClick={() => setMobileSection('panel')}
        >
          Panel
        </button>
      </section>

      <main className="clinician-main-one-page">
        <div className="clinician-layout clinician-layout-three">
          {/* Left: patient list + recent uploads */}
          <aside className="clinician-sidebar" aria-busy={isQueueLoading}>
            {loadError && (
              <div className="clinician-load-error">
                <p>{loadError}</p>
                <button type="button" className="ghost-button compact" onClick={loadPatientListAndUploads}>
                  Retry
                </button>
              </div>
            )}
            <div className={`clinician-sidebar-intro ${mobileSection !== 'queue' ? 'clinician-mobile-collapsed' : ''}`}>
              <h2>Patient queue</h2>
              <p>Request access, monitor approvals, and open active workspaces from one flow.</p>
            </div>
            <section className={`clinician-section clinician-link-patient clinician-sidebar-card ${mobileSection !== 'link' ? 'clinician-mobile-collapsed' : ''}`}>
              <h2>Link a patient</h2>
              <p className="clinician-link-hint">Enter the patient ID to request access. The patient must approve in their MedMemory account.</p>
              <form onSubmit={handleRequestAccess} className="clinician-request-form">
                <label className="clinician-request-label">
                  Patient ID
                  <input
                    ref={requestPatientInputRef}
                    type="number"
                    min={1}
                    value={requestPatientId}
                    onChange={(e) => { setRequestPatientId(e.target.value); setRequestAccessError(null); }}
                    placeholder="e.g. 1"
                    disabled={requestAccessLoading}
                    className="clinician-request-input"
                  />
                </label>
                {requestAccessError && (
                  <p className="clinician-request-error" role="alert">{requestAccessError}</p>
                )}
                <button
                  type="submit"
                  className="primary-button clinician-request-btn"
                  disabled={requestAccessLoading || !requestPatientId.trim()}
                >
                  {requestAccessLoading ? 'Requesting…' : 'Request access'}
                </button>
              </form>
            </section>
            <section className={`clinician-section clinician-sidebar-card ${mobileSection !== 'queue' ? 'clinician-mobile-collapsed' : ''}`}>
              <div className="clinician-section-heading">
                <h2>Linked patients</h2>
                <span className="clinician-section-count">{patients.length}</span>
              </div>
              {patients.length > 0 && (
                <div className="clinician-inline-search">
                  <input
                    type="search"
                    value={patientSearchTerm}
                    onChange={(e) => setPatientSearchTerm(e.target.value)}
                    placeholder="Search name or ID"
                    className="clinician-request-input clinician-search-input"
                    aria-label="Search linked patients"
                  />
                </div>
              )}
              {loadingPatients ? (
                <p className="clinician-loading"><span className="clinician-loading-spinner" aria-hidden /> Loading…</p>
              ) : patients.length === 0 ? (
                <p className="clinician-empty">No patients linked yet. Use “Link a patient” above to request access.</p>
              ) : filteredPatients.length === 0 ? (
                <p className="clinician-empty">
                  No matches for “{patientSearchTerm.trim()}”.
                </p>
              ) : (
                <ul className="clinician-patient-list">
                  {filteredPatients.map((p) => {
                    const isActive = p.grant_status === 'active';
                    return (
                      <li key={p.grant_id}>
                        <button
                          type="button"
                          className={`clinician-patient-card ${selectedPatientId === p.patient_id ? 'selected' : ''} ${!isActive ? 'clinician-patient-pending' : ''}`}
                          onClick={() => isActive && handleSelectPatient(p.patient_id, p.patient_full_name)}
                          disabled={!isActive}
                          title={!isActive ? 'Waiting for patient approval' : undefined}
                        >
                          <strong>{p.patient_full_name}</strong>
                          <span className="clinician-meta">Patient ID: {p.patient_id}</span>
                          <span className={`clinician-meta clinician-grant-status clinician-grant-${p.grant_status}`}>
                            {p.grant_status === 'active' ? 'Active – can view' : p.grant_status === 'pending' ? 'Pending – waiting for approval' : p.grant_status}
                          </span>
                          {p.expires_at && isActive && (
                            <span className="clinician-meta">
                              Expires: {new Date(p.expires_at).toLocaleDateString()}
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
            <section className={`clinician-section clinician-sidebar-card ${mobileSection !== 'queue' ? 'clinician-mobile-collapsed' : ''}`}>
              <div className="clinician-section-heading">
                <h2>Recent uploads</h2>
                <span className="clinician-section-count">{uploads.length}</span>
              </div>
              {loadingUploads ? (
                <p className="clinician-loading"><span className="clinician-loading-spinner" aria-hidden /> Loading…</p>
              ) : uploads.length === 0 ? (
                <p className="clinician-empty">No documents yet.</p>
              ) : (
                <ul className="clinician-upload-list">
                  {uploads.slice(0, 20).map((doc) => (
                    <li key={doc.id}>
                      <span className="clinician-upload-title">{doc.title || doc.original_filename}</span>
                      <span className="clinician-meta">Patient ID: {doc.patient_id}</span>
                      <span className="clinician-meta">{doc.processing_status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>

          {/* Center: chat (like patient portal) */}
          <div className="clinician-chat-center">
            {selectedPatientId === null ? (
              <div className="clinician-workspace-placeholder clinician-workspace-welcome">
                <div className={`clinician-welcome-hero ${showWorkspaceChecklist ? '' : 'is-compact'}`} aria-labelledby="clinician-welcome-title">
                  <span className="clinician-welcome-kicker">Quick start</span>
                  <h2 className="clinician-welcome-title" id="clinician-welcome-title">Start with a patient workspace</h2>
                  <p className="clinician-welcome-text">Request or open a linked patient from the left column, then use chat and records side by side.</p>
                  <div className="clinician-welcome-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={handleFocusLinkPatient}
                    >
                      Enter patient ID
                    </button>
                    <button
                      type="button"
                      className="ghost-button compact"
                      onClick={() => setShowWorkspaceChecklist((show) => !show)}
                    >
                      {showWorkspaceChecklist ? 'Hide checklist' : 'Show checklist'}
                    </button>
                  </div>
                  {!showWorkspaceChecklist && (
                    <p className="clinician-welcome-compact-hint">
                      Use the top action bar to open the first active patient when one is available.
                    </p>
                  )}
                  {showWorkspaceChecklist && (
                    <div className="clinician-welcome-track" aria-label="Workspace setup progress">
                      {onboardingSteps.map((step, index) => (
                        <article key={step.key} className={`clinician-welcome-track-item step-${step.state}`}>
                          <span className="clinician-welcome-track-index" aria-hidden>
                            {index + 1}
                          </span>
                          <div className="clinician-welcome-track-copy">
                            <strong>{step.title}</strong>
                            <span>{step.detail}</span>
                          </div>
                          <span className="clinician-welcome-track-state">{ONBOARDING_STEP_LABEL[step.state]}</span>
                        </article>
                      ))}
                    </div>
                  )}
                  {activePatients.length === 0 && pendingPatients.length > 0 && (
                    <p className="clinician-welcome-footnote">
                      You have pending requests. Once approved, patients become selectable from the left panel.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="clinician-chat-wrapper">
                <div className="clinician-chat-header">
                  <span className="clinician-chat-patient-badge">{selectedPatientName}</span>
                  <button type="button" className="clinician-chat-back" onClick={handleBackToList}>
                    Change patient
                  </button>
                </div>
                <p className="clinician-chat-hint-inline">Terse, cited answers. Say “Not in documents” when missing.</p>
                <ChatInterface
                  messages={messages}
                  question={question}
                  isStreaming={isStreaming}
                  isDisabled={false}
                  selectedPatient={{ id: selectedPatientId, full_name: selectedPatientName }}
                  showHeader={false}
                  onQuestionChange={setQuestion}
                  onSend={send}
                />
              </div>
            )}
          </div>

          {/* Right: patient panel (documents, records, dependents note) */}
          <aside className={`clinician-customer-panel clinician-panel-polished ${mobileSection !== 'panel' ? 'clinician-mobile-collapsed' : ''}`}>
            <h2 className="clinician-panel-title">Patient panel</h2>
            {selectedPatientId === null ? (
              <div className="clinician-panel-empty-state clinician-panel-empty-enhanced">
                <section className="clinician-panel-section clinician-panel-card">
                  <h3>{nextStepTitle}</h3>
                  <p className="clinician-empty clinician-empty-friendly">
                    {nextStepDescription}
                  </p>
                  <p className="clinician-next-step-status">{queueSyncLabel}</p>
                  <div className="clinician-next-step-actions">
                    <button
                      type="button"
                      className="ghost-button compact"
                      onClick={() => setShowQueueInsights((show) => !show)}
                    >
                      {showQueueInsights ? 'Hide queue details' : 'Show queue details'}
                    </button>
                  </div>
                </section>
                {showQueueInsights && (
                  <>
                    {pendingPatients.length > 0 && (
                      <section className="clinician-panel-section clinician-panel-card">
                        <h3>Pending approvals</h3>
                        <ul className="clinician-panel-list">
                          {pendingPatients.slice(0, 4).map((pending) => (
                            <li key={pending.grant_id}>
                              <strong>{pending.patient_full_name}</strong>
                              <span className="clinician-meta">Patient ID: {pending.patient_id}</span>
                              <span className="clinician-meta">Waiting for approval</span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}
                    {recentUploadsPreview.length > 0 && (
                      <section className="clinician-panel-section clinician-panel-card">
                        <h3>Latest uploads</h3>
                        <ul className="clinician-panel-list">
                          {recentUploadsPreview.map((doc) => (
                            <li key={doc.id}>
                              <strong>{doc.title || doc.original_filename}</strong>
                              <span className="clinician-meta">Patient ID: {doc.patient_id}</span>
                              <span className="clinician-meta">{doc.processing_status}</span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}
                  </>
                )}
              </div>
            ) : (
              <>
                <div className="clinician-panel-patient-badge">
                  <span className="clinician-panel-patient-name">{selectedPatientName}</span>
                  <span className="clinician-panel-patient-id">ID: {selectedPatientId}</span>
                </div>
                <div className="clinician-panel-stats" aria-label="Selected patient stats">
                  <span><strong>{documents.length}</strong> documents</span>
                  <span><strong>{records.length}</strong> records</span>
                </div>
                <section className="clinician-panel-section clinician-panel-card">
                  <h3>Documents</h3>
                  {loadingDocs ? (
                    <p className="clinician-loading"><span className="clinician-loading-spinner" aria-hidden /> Loading…</p>
                  ) : documents.length === 0 ? (
                    <p className="clinician-empty clinician-empty-friendly">No documents yet. The patient can upload from their MedMemory account.</p>
                  ) : (
                    <ul className="clinician-doc-list clinician-panel-list">
                      {documents.map((d) => (
                        <li key={d.id}>
                          <strong>{d.title || d.original_filename}</strong>
                          <span className="clinician-meta">{d.processing_status}</span>
                          <span className="clinician-meta">
                            {formatDate((d as { received_date?: string; created_at?: string }).received_date ?? (d as { created_at?: string }).created_at ?? '')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                <section className="clinician-panel-section clinician-panel-card">
                  <h3>Records</h3>
                  {loadingRecords ? (
                    <p className="clinician-loading"><span className="clinician-loading-spinner" aria-hidden /> Loading…</p>
                  ) : records.length === 0 ? (
                    <p className="clinician-empty clinician-empty-friendly">No clinical notes yet.</p>
                  ) : (
                    <ul className="clinician-record-list clinician-panel-list">
                      {records.map((r) => (
                        <li key={r.id}>
                          <strong>{r.title}</strong>
                          <span className="clinician-meta">{formatDate(r.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                <section className="clinician-panel-section clinician-panel-card clinician-dependents-note">
                  <h3>Dependents</h3>
                  <p className="clinician-dependents-text">
                    This patient may have family members (dependents) linked in their account. Access is per profile—request access to each person&apos;s Patient ID separately to view their records.
                  </p>
                </section>
              </>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
