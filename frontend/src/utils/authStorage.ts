export type PortalAuthContext = 'patient' | 'clinician';

type AuthStorageKeys = {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
};

// The refresh token itself lives in an httpOnly cookie set by the backend;
// only the short-lived access token and its expiry are kept in localStorage.
// refreshToken keys remain solely to migrate/clear tokens stored by older builds.
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

export const readLegacyRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  const keys = getAuthStorageKeys();
  return window.localStorage.getItem(keys.refreshToken);
};

export const clearLegacyRefreshToken = (): void => {
  if (typeof window === 'undefined') return;
  const keys = getAuthStorageKeys();
  window.localStorage.removeItem(keys.refreshToken);
};

export const readActiveTokenExpiresAt = (): number | null => {
  if (typeof window === 'undefined') return null;
  const keys = getAuthStorageKeys();
  const value = window.localStorage.getItem(keys.expiresAt);
  return value ? Number.parseInt(value, 10) : null;
};

export const writeActiveAuthTokens = (
  accessToken: string,
  expiresAt: number,
): void => {
  if (typeof window === 'undefined') return;
  const keys = getAuthStorageKeys();
  window.localStorage.setItem(keys.accessToken, accessToken);
  window.localStorage.setItem(keys.expiresAt, String(expiresAt));
  window.localStorage.removeItem(keys.refreshToken);
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
