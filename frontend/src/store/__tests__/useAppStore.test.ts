import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const importFreshStore = async () => {
  vi.resetModules();
  return (await import('../useAppStore')).default;
};

describe('useAppStore', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    window.history.pushState({}, '', '/');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    window.history.pushState({}, '', '/');
  });

  it('hydrates clinician auth state from local storage', async () => {
    localStorage.setItem('medmemory_api_key', 'api-key-1');
    localStorage.setItem('medmemory_clinician', '1');
    localStorage.setItem('medmemory_clinician_access_token', 'clinician-access');
    localStorage.setItem('medmemory_clinician_refresh_token', 'clinician-refresh');
    localStorage.setItem('medmemory_theme', 'dark');
    window.history.pushState({}, '', '/clinician');

    const useAppStore = await importFreshStore();
    const state = useAppStore.getState();

    expect(state.apiKey).toBe('api-key-1');
    expect(state.accessToken).toBe('clinician-access');
    expect(state.refreshToken).toBe('clinician-refresh');
    expect(state.isAuthenticated).toBe(true);
    expect(state.isClinician).toBe(true);
    expect(state.theme).toBe('dark');
  });

  it('writes token state and clears it when access token is removed', async () => {
    const dateNow = vi.spyOn(Date, 'now').mockReturnValue(1_000);
    const useAppStore = await importFreshStore();

    useAppStore.setState({
      patientId: 12,
      patientSearch: 'alice',
      user: {
        id: 9,
        email: 'user@example.com',
        full_name: 'Test User',
        is_active: true,
      },
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
      tokenExpiresAt: null,
    });
    useAppStore.getState().setTokens('patient-access', 'patient-refresh', 60);

    expect(localStorage.getItem('medmemory_access_token')).toBe('patient-access');
    expect(localStorage.getItem('medmemory_refresh_token')).toBe('patient-refresh');
    expect(localStorage.getItem('medmemory_token_expires_at')).toBe('61000');
    expect(useAppStore.getState().tokenExpiresAt).toBe(61_000);
    expect(useAppStore.getState().isAuthenticated).toBe(true);

    useAppStore.getState().setAccessToken(null);

    expect(useAppStore.getState().accessToken).toBeNull();
    expect(useAppStore.getState().refreshToken).toBeNull();
    expect(useAppStore.getState().patientId).toBe(0);
    expect(useAppStore.getState().patientSearch).toBe('');
    expect(useAppStore.getState().user).toBeNull();
    expect(useAppStore.getState().isAuthenticated).toBe(false);
    expect(localStorage.getItem('medmemory_access_token')).toBeNull();
    expect(localStorage.getItem('medmemory_refresh_token')).toBeNull();

    dateNow.mockRestore();
  });

  it('updates clinician and theme state and clears everything on logout', async () => {
    const matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
    vi.stubGlobal('matchMedia', matchMedia);

    const useAppStore = await importFreshStore();
    useAppStore.setState({
      patientId: 5,
      patientSearch: 'jamie',
      accessToken: 'token-1',
      refreshToken: 'refresh-1',
      tokenExpiresAt: 123,
      isAuthenticated: true,
      isClinician: false,
      user: {
        id: 5,
        email: 'jamie@example.com',
        full_name: 'Jamie Doe',
        is_active: true,
      },
    });

    useAppStore.getState().setClinician(true);
    expect(localStorage.getItem('medmemory_clinician')).toBe('1');
    expect(useAppStore.getState().isClinician).toBe(true);

    useAppStore.getState().setTheme('system');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(useAppStore.getState().theme).toBe('system');

    useAppStore.getState().logout();

    expect(useAppStore.getState().accessToken).toBeNull();
    expect(useAppStore.getState().refreshToken).toBeNull();
    expect(useAppStore.getState().user).toBeNull();
    expect(useAppStore.getState().isClinician).toBe(false);
    expect(useAppStore.getState().isAuthenticated).toBe(false);
    expect(localStorage.getItem('medmemory_clinician')).toBeNull();
  });
});
