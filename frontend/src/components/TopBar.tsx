import { useEffect, useRef, useState } from 'react';
import LoginModal from './LoginModal';
import SignUpModal from './SignUpModal';
import ForgotPasswordModal from './ForgotPasswordModal';
import ResetPasswordModal from './ResetPasswordModal';
import useAppStore from '../store/useAppStore';
import { api } from '../api';

type TopBarProps = {
  viewMode?: 'chat' | 'dashboard';
  onViewChange?: (mode: 'chat' | 'dashboard') => void;
  patientMeta?: { age?: number | null; gender?: string | null } | null;
};

const TopBar = ({ viewMode, onViewChange, patientMeta }: TopBarProps) => {
  const [showLogin, setShowLogin] = useState(false);
  const [showSignup, setShowSignup] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const user = useAppStore((state) => state.user);
  const logout = useAppStore((state) => state.logout);
  const theme = useAppStore((state) => state.theme);
  const setTheme = useAppStore((state) => state.setTheme);

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

  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, [menuOpen]);

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

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <span className="brand-dot" />
            <span>MedMemory</span>
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
                  <span className="user-label">{user?.full_name || user?.email}</span>
                </button>
                {menuOpen ? (
                  <div className="user-dropdown" role="menu">
                    <div className="user-meta">
                      <strong>{user?.full_name || 'Patient'}</strong>
                      <span>{user?.email}</span>
                    </div>
                    {patientMeta ? (
                      patientMeta.age || patientMeta.gender ? (
                        <div className="user-details">
                          {patientMeta.age ? (
                            <span>Age {patientMeta.age}</span>
                          ) : (
                            <span className="empty">Age not set</span>
                          )}
                          {patientMeta.gender ? (
                            <span>{patientMeta.gender}</span>
                          ) : (
                            <span className="empty">Gender not set</span>
                          )}
                        </div>
                      ) : (
                        <div className="user-details empty-state">
                          <span>Profile details missing.</span>
                        </div>
                      )
                    ) : null}
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
                Log In
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={() => setShowSignup(true)}
                data-testid="open-signup"
              >
                Sign Up
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
      />
      <SignUpModal
        isOpen={showSignup}
        onClose={() => setShowSignup(false)}
        onSwitchToLogin={() => {
          setShowSignup(false);
          setShowLogin(true);
        }}
      />
      <ForgotPasswordModal
        isOpen={showForgot}
        onClose={() => setShowForgot(false)}
        onSwitchToReset={() => {
          setShowForgot(false);
          setShowReset(true);
        }}
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
    </>
  );
};

export default TopBar;
