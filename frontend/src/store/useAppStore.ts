import { create } from 'zustand';
import {
  clearActiveAuthTokens,
  readActiveAccessToken,
  readActiveRefreshToken,
  writeActiveAccessToken,
  writeActiveAuthTokens,
} from '../utils/authStorage';

const getInitialToken = () => {
  return readActiveAccessToken();
};

const getInitialRefreshToken = () => {
  return readActiveRefreshToken();
};

const getInitialApiKey = () => {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('medmemory_api_key') || '';
};

const getInitialIsClinician = () => {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem('medmemory_clinician') === '1';
};

type User = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
} | null;

type AppState = {
  patientId: number;
  patientSearch: string;
  apiKey: string;
  accessToken: string | null;
  refreshToken: string | null;
  tokenExpiresAt: number | null;
  user: User;
  isAuthenticated: boolean;
  isClinician: boolean;
  theme: 'light' | 'dark' | 'system';
  setPatientId: (value: number) => void;
  setPatientSearch: (value: string) => void;
  setApiKey: (value: string) => void;
  setTokens: (accessToken: string, refreshToken: string, expiresIn: number) => void;
  setAccessToken: (token: string | null) => void;
  setUser: (user: User) => void;
  setClinician: (value: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  logout: () => void;
};

const useAppStore = create<AppState>((set) => ({
  patientId: 0,
  patientSearch: '',
  apiKey: getInitialApiKey(),
  accessToken: getInitialToken(),
  refreshToken: getInitialRefreshToken(),
  tokenExpiresAt: null,
  user: null,
  isAuthenticated: !!getInitialToken(),
  isClinician: getInitialIsClinician(),
  theme: (typeof window !== 'undefined' && localStorage.getItem('medmemory_theme') as 'light' | 'dark' | 'system') || 'system',
  setPatientId: (value) => set({ patientId: value }),
  setPatientSearch: (value) => set({ patientSearch: value }),
  setApiKey: (value) => {
    if (typeof window !== 'undefined') {
      if (value) {
        window.localStorage.setItem('medmemory_api_key', value);
      } else {
        window.localStorage.removeItem('medmemory_api_key');
      }
    }
    set({ apiKey: value });
  },
  setTokens: (accessToken, refreshToken, expiresIn) => {
    const expiresAt = Date.now() + expiresIn * 1000;
    writeActiveAuthTokens(accessToken, refreshToken, expiresAt);
    set({
      accessToken,
      refreshToken,
      tokenExpiresAt: expiresAt,
      isAuthenticated: true,
    });
  },
  setAccessToken: (token) => {
    if (token) writeActiveAccessToken(token);
    else clearActiveAuthTokens();
    if (!token) {
      set({
        accessToken: null,
        refreshToken: null,
        tokenExpiresAt: null,
        isAuthenticated: false,
        user: null,
        patientId: 0,
        patientSearch: '',
      });
      return;
    }
    set({ accessToken: token, isAuthenticated: true });
  },
  setUser: (user) => set({ user }),
  setClinician: (value) => {
    if (typeof window !== 'undefined') {
      if (value) window.localStorage.setItem('medmemory_clinician', '1');
      else window.localStorage.removeItem('medmemory_clinician');
    }
    set({ isClinician: value });
  },
  setTheme: (theme) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medmemory_theme', theme);
      const root = document.documentElement;
      if (theme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
      } else {
        root.setAttribute('data-theme', theme);
      }
    }
    set({ theme });
  },
  logout: () => {
    clearActiveAuthTokens();
    if (typeof window !== 'undefined') window.localStorage.removeItem('medmemory_clinician');
    set({
      accessToken: null,
      refreshToken: null,
      tokenExpiresAt: null,
      user: null,
      isAuthenticated: false,
      isClinician: false,
      patientId: 0,
      patientSearch: '',
    });
  },
}));

export default useAppStore;
