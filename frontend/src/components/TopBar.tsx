import { useState } from 'react';
import LoginModal from './LoginModal';
import SignUpModal from './SignUpModal';
import useAppStore from '../store/useAppStore';

const TopBar = () => {
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
              <span className="user-name">{user?.full_name || user?.email}</span>
              <button className="ghost-button" type="button" onClick={handleLogout}>
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
