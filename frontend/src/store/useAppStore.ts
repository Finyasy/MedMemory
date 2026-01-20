import { create } from 'zustand';

const getInitialToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_access_token');
};

const getInitialApiKey = () => {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('medmemory_api_key') || '';
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
  user: User;
  isAuthenticated: boolean;
  setPatientId: (value: number) => void;
  setPatientSearch: (value: string) => void;
  setApiKey: (value: string) => void;
  setAccessToken: (token: string | null) => void;
  setUser: (user: User) => void;
  logout: () => void;
};

const useAppStore = create<AppState>((set) => ({
  patientId: 0,
  patientSearch: '',
  apiKey: getInitialApiKey(),
  accessToken: getInitialToken(),
  user: null,
  isAuthenticated: !!getInitialToken(),
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
  setAccessToken: (token) => {
    if (typeof window !== 'undefined') {
      if (token) {
        window.localStorage.setItem('medmemory_access_token', token);
      } else {
        window.localStorage.removeItem('medmemory_access_token');
      }
    }
    if (!token) {
      set({
        accessToken: null,
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
  logout: () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('medmemory_access_token');
    }
    set({ accessToken: null, user: null, isAuthenticated: false, patientId: 0, patientSearch: '' });
  },
}));

export default useAppStore;
