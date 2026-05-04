export type PortalAuthContext = 'patient' | 'clinician';

type AuthStorageKeys = {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
};

const PATIENT_KEYS: AuthStorageKeys = {
  accessToken: 'medmemory_access_token',
  refreshToken: 'medmemory_refresh_token',
  expiresAt: 'medmemory_token_expires_at',
};

const CLINICIAN_KEYS: AuthStorageKeys = {
  accessToken: 'medmemory_clinician_access_token',
  refreshToken: 'medmemory_clinician_refresh_token',
  expiresAt: 'medmemory_clinician_token_expires_at',
};

export const getActivePortalAuthContext = (): PortalAuthContext => {
  if (typeof window === 'undefined') return 'patient';
  return window.location.pathname.startsWith('/clinician') ? 'clinician' : 'patient';
};

export const getAuthStorageKeys = (
  context: PortalAuthContext = getActivePortalAuthContext(),
): AuthStorageKeys => {
  return context === 'clinician' ? CLINICIAN_KEYS : PATIENT_KEYS;
};

export const readActiveAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  const keys = getAuthStorageKeys();
  return window.localStorage.getItem(keys.accessToken);
};

export const readActiveRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  const keys = getAuthStorageKeys();
  return window.localStorage.getItem(keys.refreshToken);
};

export const readActiveTokenExpiresAt = (): number | null => {
  if (typeof window === 'undefined') return null;
  const keys = getAuthStorageKeys();
  const value = window.localStorage.getItem(keys.expiresAt);
  return value ? Number.parseInt(value, 10) : null;
};

export const writeActiveAuthTokens = (
  accessToken: string,
  refreshToken: string,
  expiresAt: number,
): void => {
  if (typeof window === 'undefined') return;
  const keys = getAuthStorageKeys();
  window.localStorage.setItem(keys.accessToken, accessToken);
  window.localStorage.setItem(keys.refreshToken, refreshToken);
  window.localStorage.setItem(keys.expiresAt, String(expiresAt));
};

export const writeActiveAccessToken = (token: string): void => {
  if (typeof window === 'undefined') return;
  const keys = getAuthStorageKeys();
  window.localStorage.setItem(keys.accessToken, token);
};

export const clearActiveAuthTokens = (): void => {
  if (typeof window === 'undefined') return;
  const keys = getAuthStorageKeys();
  window.localStorage.removeItem(keys.accessToken);
  window.localStorage.removeItem(keys.refreshToken);
  window.localStorage.removeItem(keys.expiresAt);
};
