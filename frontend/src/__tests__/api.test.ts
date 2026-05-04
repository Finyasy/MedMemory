import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api, buildBackendUrl, getUserFriendlyMessage } from '../api';

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('api', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('buildBackendUrl preserves absolute urls and prefixes relative paths', () => {
    expect(buildBackendUrl('http://example.com/file')).toBe('http://example.com/file');
    expect(buildBackendUrl('/health')).toBe('http://localhost:3000/health');
    expect(buildBackendUrl('api/v1/profile')).toBe(
      'http://localhost:3000/api/v1/profile',
    );
  });

  it('getUserFriendlyMessage maps auth and network failures to patient-facing copy', () => {
    window.localStorage.setItem('medmemory_access_token', 'token-1');
    expect(getUserFriendlyMessage(new ApiError(401, 'Not authenticated'))).toBe(
      'Your session has expired. Please sign in again.',
    );

    window.localStorage.clear();
    expect(getUserFriendlyMessage(new ApiError(401, 'Not authenticated'))).toBe(
      'Invalid email or password.',
    );
    expect(getUserFriendlyMessage(new ApiError(0, 'offline'))).toBe(
      'Unable to reach the server. Please check your connection or try again.',
    );
    expect(getUserFriendlyMessage(new Error('boom'))).toBe('boom');
  });

  it('forgotPassword retries alternate recovery urls after a 404', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ detail: 'missing' }, 404))
      .mockResolvedValueOnce(jsonResponse({ message: 'Reset link sent' }));

    await expect(api.forgotPassword('demo@example.com')).resolves.toEqual({
      message: 'Reset link sent',
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      'http://localhost:3000/api/v1/auth/forgot-password',
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      'http://localhost:3000/auth/forgot-password',
    );
  });

  it('getProfile and getConversation include bearer auth headers', async () => {
    window.localStorage.setItem('medmemory_access_token', 'token-123');
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url =
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url === '/api/v1/profile?patient_id=7') {
          return jsonResponse({ id: 7, full_name: 'Patient Seven', is_dependent: false });
        }
        if (url === '/api/v1/chat/conversations/conv-1') {
          return jsonResponse({
            conversation_id: 'conv-1',
            patient_id: 7,
            title: 'Check-in',
            created_at: '2026-03-13T08:00:00Z',
            updated_at: '2026-03-13T08:01:00Z',
            message_count: 1,
            messages: [
              {
                role: 'assistant',
                content: 'Here is your summary.',
                timestamp: '2026-03-13T08:01:00Z',
                structured_data: { overview: 'Structured card' },
              },
            ],
          });
        }
        return jsonResponse({ detail: 'missing' }, 404);
      });

    const profile = await api.getProfile(7);
    const conversation = await api.getConversation('conv-1');

    expect(profile.full_name).toBe('Patient Seven');
    expect(conversation.messages[0]?.structured_data).toEqual({
      overview: 'Structured card',
    });
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: { Authorization: 'Bearer token-123' },
      method: 'GET',
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      headers: { Authorization: 'Bearer token-123' },
      method: 'GET',
    });
  });

  it('wraps fetch transport failures in ApiError with status 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('fetch failed'));

    await expect(api.listDependents()).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    });
  });
});
