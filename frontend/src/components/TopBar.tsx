import { useEffect, useRef, useState, useCallback } from 'react';
import LoginModal from './LoginModal';
import SignUpModal from './SignUpModal';
import ForgotPasswordModal from './ForgotPasswordModal';
import ResetPasswordModal from './ResetPasswordModal';
import ProfileModal from './ProfileModal';
import AddDependentModal from './AddDependentModal';
import useAppStore from '../store/useAppStore';
import useToast from '../hooks/useToast';
import { api, buildBackendUrl } from '../api';

type BackendStatus = 'checking' | 'online' | 'offline';

type AccessRequestItem = {
  grant_id: number;
  patient_id: number;
  patient_name: string;
  clinician_user_id: number;
  clinician_name: string;
  clinician_email: string;
  status: string;
  scopes: string;
  created_at: string;
};

type Dependent = {
  id: number;
  full_name: string;
  age: number | null;
  sex: string | null;
  relationship_type: string;
};

type TopBarProps = {
  backendStatus?: BackendStatus;
  viewMode?: 'chat' | 'dashboard';
  onViewChange?: (mode: 'chat' | 'dashboard') => void;
  patientMeta?: { age?: number | null; gender?: string | null } | null;
  selectedPatientId?: number | null;
  onPatientChange?: (patientId: number | null) => void;
  onDependentAdded?: (dependentId: number, dependentName: string) => void;
};

const TopBar = ({
  backendStatus = 'checking',
  viewMode,
  onViewChange,
  patientMeta: _patientMeta,
  selectedPatientId,
  onPatientChange,
  onDependentAdded,
}: TopBarProps) => {
  void _patientMeta;
  const [showLogin, setShowLogin] = useState(false);
  const [showSignup, setShowSignup] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showAddDependent, setShowAddDependent] = useState(false);
  const [editingProfileId, setEditingProfileId] = useState<number | undefined>(undefined);
  const [resetToken, setResetToken] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileSwitcherOpen, setProfileSwitcherOpen] = useState(false);
  const [dependents, setDependents] = useState<Dependent[]>([]);
  const [primaryPatientId, setPrimaryPatientId] = useState<number | null>(null);
  const [primaryPatientName, setPrimaryPatientName] = useState<string>('My Health');
  const [accessRequests, setAccessRequests] = useState<AccessRequestItem[]>([]);
  const [accessRequestsLoading, setAccessRequestsLoading] = useState(false);
  const [accessRequestsOpen, setAccessRequestsOpen] = useState(false);
  const [actingGrantId, setActingGrantId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const switcherRef = useRef<HTMLDivElement | null>(null);
  const accessRequestsRef = useRef<HTMLDivElement | null>(null);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const { pushToast } = useToast();
  const user = useAppStore((state) => state.user);
  const logout = useAppStore((state) => state.logout);
  const theme = useAppStore((state) => state.theme);
  const setTheme = useAppStore((state) => state.setTheme);

  const loadDependents = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const headers = await api.getAuthHeaders();
      const res = await fetch(buildBackendUrl('/api/v1/dependents'), { headers });
      if (res.ok) {
        const data = await res.json();
        setDependents(data);
      }
    } catch (error) {
      console.error('Failed to load dependents', error);
    }
  }, [isAuthenticated]);

  const loadPrimaryPatient = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const headers = await api.getAuthHeaders();
      const res = await fetch(buildBackendUrl('/api/v1/profile'), { headers });
      if (res.ok) {
        const data = await res.json();
        if (typeof data?.id === 'number') {
          setPrimaryPatientId(data.id);
        }
        if (data?.full_name) {
          setPrimaryPatientName(data.full_name);
        }
      }
    } catch {
      // Silently fail
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadDependents();
      loadPrimaryPatient();
    }
  }, [isAuthenticated, loadDependents, loadPrimaryPatient]);

  const loadAccessRequests = useCallback(async () => {
    if (!isAuthenticated) return;
    setAccessRequestsLoading(true);
    try {
      const list = await api.listPatientAccessRequests();
      setAccessRequests(list);
    } catch {
      setAccessRequests([]);
    } finally {
      setAccessRequestsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) loadAccessRequests();
  }, [isAuthenticated, loadAccessRequests]);

  useEffect(() => {
    if (accessRequestsOpen) loadAccessRequests();
  }, [accessRequestsOpen, loadAccessRequests]);

  const handleApproveAccess = useCallback(async (grantId: number) => {
    setActingGrantId(grantId);
    try {
      await api.patientAccessGrant({ grant_id: grantId });
      pushToast('success', 'Access approved. The clinician can now view this profile.');
      await loadAccessRequests();
    } catch (err) {
      pushToast('error', err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setActingGrantId(null);
    }
  }, [pushToast, loadAccessRequests]);

  const handleDenyAccess = useCallback(async (grantId: number) => {
    setActingGrantId(grantId);
    try {
      await api.patientAccessRevoke({ grant_id: grantId });
      pushToast('success', 'Access request denied.');
      await loadAccessRequests();
    } catch (err) {
      pushToast('error', err instanceof Error ? err.message : 'Failed to deny');
    } finally {
      setActingGrantId(null);
    }
  }, [pushToast, loadAccessRequests]);

  const pendingCount = accessRequests.filter((r) => r.status === 'pending').length;

  const handleLogout = async () => {
    setMenuOpen(false);
    try {
      await api.logout();
    } catch {
      // Ignore logout errors
    }
    logout();
  };

  const cycleTheme = () => {
    const next = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(next);
  };

  const themeLabel = theme === 'light' ? '☀️ Light' : theme === 'dark' ? '🌙 Dark' : '💻 System';
  const backendStatusLabel = backendStatus === 'online'
    ? 'Backend online'
    : backendStatus === 'offline'
      ? 'Backend offline'
      : 'Checking backend';

  useEffect(() => {
    if (!menuOpen && !profileSwitcherOpen && !accessRequestsOpen) return;
    const handleClick = (event: MouseEvent) => {
      if (menuOpen && menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
      if (profileSwitcherOpen && switcherRef.current && !switcherRef.current.contains(event.target as Node)) {
        setProfileSwitcherOpen(false);
      }
      if (accessRequestsOpen && accessRequestsRef.current && !accessRequestsRef.current.contains(event.target as Node)) {
        setAccessRequestsOpen(false);
      }
    };
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, [menuOpen, profileSwitcherOpen, accessRequestsOpen]);

  useEffect(() => {
    setMenuOpen(false);
  }, [isAuthenticated, user?.id]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (url.pathname === '/reset-password') {
      const token = url.searchParams.get('token') || '';
      setResetToken(token);
      setShowReset(true);
      setShowLogin(false);
      setShowSignup(false);
      setShowForgot(false);
    }
  }, []);

  useEffect(() => {
    const handleOpenProfile = (event: Event) => {
      const customEvent = event as CustomEvent<{ patientId?: number | null }>;
      const targetId = customEvent.detail?.patientId;
      setEditingProfileId(typeof targetId === 'number' ? targetId : undefined);
      setShowProfile(true);
    };
    window.addEventListener('medmemory:open-profile', handleOpenProfile);
    return () => window.removeEventListener('medmemory:open-profile', handleOpenProfile);
  }, []);

  useEffect(() => {
    const openLogin = () => {
      setShowSignup(false);
      setShowLogin(true);
    };
    const openSignup = () => {
      setShowLogin(false);
      setShowSignup(true);
    };
    window.addEventListener('medmemory:open-login', openLogin);
    window.addEventListener('medmemory:open-signup', openSignup);
    return () => {
      window.removeEventListener('medmemory:open-login', openLogin);
      window.removeEventListener('medmemory:open-signup', openSignup);
    };
  }, []);

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <span className="brand-dot" />
            <span>MedMemory</span>
          </div>
          <div className="status-chip" role="status" aria-live="polite">
            <span className={`status-indicator ${backendStatus}`} />
            <span>{backendStatusLabel}</span>
          </div>
        </div>
        <div className="top-actions">
          {isAuthenticated ? (
            <>
              {onViewChange ? (
                <div className="view-toggle" role="tablist" aria-label="App view">
                  <button
                    className={viewMode === 'chat' ? 'active' : ''}
                    type="button"
                    role="tab"
                    aria-selected={viewMode === 'chat'}
                    onClick={() => onViewChange('chat')}
                  >
                    Chat
                  </button>
                  <button
                    className={viewMode === 'dashboard' ? 'active' : ''}
                    type="button"
                    role="tab"
                    aria-selected={viewMode === 'dashboard'}
                    onClick={() => onViewChange('dashboard')}
                  >
                    Dashboard
                  </button>
                </div>
              ) : null}

              <div className="access-requests-trigger" ref={accessRequestsRef}>
                <button
                  type="button"
                  className="access-requests-btn"
                  onClick={() => setAccessRequestsOpen((o) => !o)}
                  aria-label={pendingCount > 0 ? `${pendingCount} clinician access request${pendingCount === 1 ? '' : 's'}` : 'Clinician access requests'}
                  aria-haspopup="dialog"
                  aria-expanded={accessRequestsOpen}
                  title="Clinician access requests"
                >
                  <span className="access-requests-icon" aria-hidden>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                      <polyline points="22,6 12,13 2,6" />
                    </svg>
                  </span>
                  {pendingCount > 0 && (
                    <span className="access-requests-badge" aria-hidden>
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </span>
                  )}
                </button>
                {accessRequestsOpen && (
                  <div className="access-requests-popover" role="dialog" aria-label="Clinician access requests">
                    <div className="access-requests-popover-header">
                      <h3>Clinician access</h3>
                      <p className="access-requests-subtitle">Your Patient ID & access requests</p>
                    </div>
                    {selectedPatientId != null && selectedPatientId > 0 && (
                      <div className="access-requests-patient-id">
                        <strong>Your Patient ID</strong>
                        <span className="access-requests-patient-id-value">{selectedPatientId}</span>
                        <span className="access-requests-patient-id-hint">Share with your clinician</span>
                      </div>
                    )}
                    <div className="access-requests-list-wrap">
                      <h4>Access requests</h4>
                      {accessRequestsLoading ? (
                        <p className="access-requests-loading">Loading…</p>
                      ) : accessRequests.length === 0 ? (
                        <p className="access-requests-empty">No access requests.</p>
                      ) : (
                        <ul className="access-requests-list-popover">
                          {accessRequests.map((req) => (
                            <li key={req.grant_id} className={`access-request-row access-request-${req.status}`}>
                              <div className="access-request-row-info">
                                <strong>{req.clinician_name}</strong>
                                <span className="access-request-row-meta">{req.clinician_email}</span>
                                <span className="access-request-row-meta">For: {req.patient_name} · {req.status}</span>
                              </div>
                              {req.status === 'pending' && (
                                <div className="access-request-row-actions">
                                  <button
                                    type="button"
                                    className="primary-button compact"
                                    disabled={actingGrantId !== null}
                                    onClick={() => handleApproveAccess(req.grant_id)}
                                  >
                                    {actingGrantId === req.grant_id ? '…' : 'Approve'}
                                  </button>
                                  <button
                                    type="button"
                                    className="secondary-button compact"
                                    disabled={actingGrantId !== null}
                                    onClick={() => handleDenyAccess(req.grant_id)}
                                  >
                                    Deny
                                  </button>
                                </div>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {onPatientChange && (
                <div className="profile-switcher" ref={switcherRef}>
                  <button
                    className="switcher-button"
                    type="button"
                    onClick={() => setProfileSwitcherOpen((open) => !open)}
                    aria-haspopup="menu"
                    aria-expanded={profileSwitcherOpen}
                  >
                    <span className="switcher-icon">👤</span>
                    <span className="switcher-label">My Health</span>
                    <span className="switcher-arrow">▼</span>
                  </button>
                  {profileSwitcherOpen && (
                    <div className="switcher-dropdown" role="menu">
                      <button
                        className="switcher-option edit-profile-option"
                        onClick={() => {
                          setProfileSwitcherOpen(false);
                          setEditingProfileId(undefined);
                          setShowProfile(true);
                        }}
                        role="menuitem"
                      >
                        <span className="option-icon">✏️</span>
                        <span className="option-label">Edit My Health Profile</span>
                      </button>
                      <div className="switcher-divider" />
                      <div className="switcher-section-label">Switch Profile</div>
                      <button
                        className={`switcher-option ${
                          !selectedPatientId || !dependents.find((d) => d.id === selectedPatientId) ? 'active' : ''
                        }`}
                        onClick={() => {
                          const targetId = primaryPatientId ?? selectedPatientId ?? 0;
                          onPatientChange(targetId);
                          setProfileSwitcherOpen(false);
                        }}
                        role="menuitem"
                      >
                        <span className="option-icon">👤</span>
                        <span className="option-label">{primaryPatientName}</span>
                        {!selectedPatientId ||
                        !dependents.find((d) => d.id === selectedPatientId) ? (
                          <span className="option-check">✓</span>
                        ) : null}
                      </button>
                      {dependents.length ? (
                        dependents.map((dep) => (
                          <div key={dep.id} className="switcher-option-row">
                            <button
                              className={`switcher-option ${selectedPatientId === dep.id ? 'active' : ''}`}
                              onClick={() => {
                                onPatientChange(dep.id);
                                setProfileSwitcherOpen(false);
                              }}
                              role="menuitem"
                            >
                              <span className="option-icon">
                                {dep.relationship_type === 'child'
                                  ? '👶'
                                  : dep.relationship_type === 'spouse'
                                    ? '💑'
                                    : dep.relationship_type === 'parent'
                                      ? '👴'
                                      : '👤'}
                              </span>
                              <span className="option-label">
                                {dep.full_name}
                                {dep.age !== null && <span className="option-age">({dep.age})</span>}
                              </span>
                              {selectedPatientId === dep.id && <span className="option-check">✓</span>}
                            </button>
                            <button
                              className="switcher-edit-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                setProfileSwitcherOpen(false);
                                setEditingProfileId(dep.id);
                                setShowProfile(true);
                              }}
                              title={`Edit ${dep.full_name}'s profile`}
                              aria-label={`Edit ${dep.full_name}'s profile`}
                            >
                              ✏️
                            </button>
                          </div>
                        ))
                      ) : null}
                      <div className="switcher-divider" />
                      <button
                        className="switcher-option add-option"
                        onClick={() => {
                          setProfileSwitcherOpen(false);
                          setShowAddDependent(true);
                        }}
                        role="menuitem"
                      >
                        <span className="option-icon">+</span>
                        <span className="option-label">Add Family Member</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="user-menu" ref={menuRef}>
                <button
                  className="user-chip"
                  type="button"
                  onClick={() => setMenuOpen((open) => !open)}
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  data-testid="user-menu"
                >
                  <span className="user-avatar">
                    {(user?.full_name || user?.email || 'U').charAt(0).toUpperCase()}
                  </span>
                </button>
                {menuOpen ? (
                  <div className="user-dropdown" role="menu">
                    <div className="user-meta">
                      <strong>{user?.full_name || 'Patient'}</strong>
                      <span>{user?.email}</span>
                    </div>
                    <div className="user-divider" />
                    <button className="ghost-button compact" type="button" onClick={cycleTheme} role="menuitem">
                      {themeLabel}
                    </button>
                    <button className="ghost-button compact" type="button" onClick={handleLogout} role="menuitem">
                      Log Out
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <button
                className="ghost-button"
                type="button"
                onClick={() => setShowLogin(true)}
                data-testid="open-login"
              >
                Patient Log In
              </button>
              <a className="ghost-button subtle topbar-clinician-link" href="/clinician">
                Clinician Portal
              </a>
              <button
                className="topbar-hidden-trigger"
                type="button"
                onClick={() => setShowSignup(true)}
                data-testid="open-signup"
                tabIndex={-1}
                aria-hidden="true"
              >
                Open Sign Up
              </button>
            </>
          )}
        </div>
      </header>
      <LoginModal
        isOpen={showLogin}
        onClose={() => setShowLogin(false)}
        onSwitchToSignup={() => {
          setShowLogin(false);
          setShowSignup(true);
        }}
        onForgotPassword={() => {
          setShowLogin(false);
          setShowForgot(true);
        }}
        backendStatus={backendStatus}
      />
      <SignUpModal
        isOpen={showSignup}
        onClose={() => setShowSignup(false)}
        onSwitchToLogin={() => {
          setShowSignup(false);
          setShowLogin(true);
        }}
        backendStatus={backendStatus}
      />
      <ForgotPasswordModal
        isOpen={showForgot}
        onClose={() => setShowForgot(false)}
        onSwitchToReset={() => {
          setShowForgot(false);
          setShowReset(true);
        }}
        backendStatus={backendStatus}
      />
      <ResetPasswordModal
        isOpen={showReset}
        onClose={() => {
          setShowReset(false);
          setResetToken('');
        }}
        onBackToLogin={() => {
          setShowReset(false);
          setResetToken('');
          setShowLogin(true);
        }}
        initialToken={resetToken}
      />
      <ProfileModal
        isOpen={showProfile}
        onClose={() => {
          setShowProfile(false);
          setEditingProfileId(undefined);
        }}
        patientId={editingProfileId}
      />
      <AddDependentModal
        isOpen={showAddDependent}
        onClose={() => setShowAddDependent(false)}
        onAdded={(dependentId, dependentName) => {
          loadDependents();
          if (onPatientChange) {
            onPatientChange(dependentId);
          }
          if (onDependentAdded) {
            onDependentAdded(dependentId, dependentName);
          }
        }}
      />
    </>
  );
};

export default TopBar;
