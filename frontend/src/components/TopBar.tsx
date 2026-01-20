import { useState } from 'react';
import LoginModal from './LoginModal';
import SignUpModal from './SignUpModal';
import useAppStore from '../store/useAppStore';

type TopBarProps = {
  viewMode?: 'chat' | 'dashboard';
  onViewChange?: (mode: 'chat' | 'dashboard') => void;
};

const TopBar = ({ viewMode, onViewChange }: TopBarProps) => {
  const [showLogin, setShowLogin] = useState(false);
  const [showSignup, setShowSignup] = useState(false);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const user = useAppStore((state) => state.user);
  const logout = useAppStore((state) => state.logout);

  const handleLogout = () => {
    logout();
  };

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
              <div className="user-chip">
                <span className="user-avatar">
                  {(user?.full_name || user?.email || 'U').charAt(0).toUpperCase()}
                </span>
                <span className="user-label">{user?.full_name || user?.email}</span>
              </div>
              <button className="ghost-button subtle" type="button" onClick={handleLogout}>
                Log Out
              </button>
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
