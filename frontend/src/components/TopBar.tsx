import { useEffect, useRef, useState } from 'react';
import LoginModal from './LoginModal';
import SignUpModal from './SignUpModal';
import useAppStore from '../store/useAppStore';

type TopBarProps = {
  viewMode?: 'chat' | 'dashboard';
  onViewChange?: (mode: 'chat' | 'dashboard') => void;
  patientMeta?: { age?: number | null; gender?: string | null } | null;
};

const TopBar = ({ viewMode, onViewChange, patientMeta }: TopBarProps) => {
  const [showLogin, setShowLogin] = useState(false);
  const [showSignup, setShowSignup] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const user = useAppStore((state) => state.user);
  const logout = useAppStore((state) => state.logout);

  const handleLogout = () => {
    logout();
  };

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
                    <button className="ghost-button compact" type="button" onClick={handleLogout} role="menuitem">
                      Log Out
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <button className="ghost-button" type="button" onClick={() => setShowLogin(true)}>
                Log In
              </button>
              <button className="primary-button" type="button" onClick={() => setShowSignup(true)}>
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
      />
      <SignUpModal
        isOpen={showSignup}
        onClose={() => setShowSignup(false)}
        onSwitchToLogin={() => {
          setShowSignup(false);
          setShowLogin(true);
        }}
      />
    </>
  );
};

export default TopBar;
