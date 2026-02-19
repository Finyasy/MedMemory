import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import TopBar from '../TopBar';
import useAppStore from '../../store/useAppStore';
import { api } from '../../api';

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  useAppStore.setState({ 
    patientId: 1, 
    patientSearch: '', 
    apiKey: '',
    accessToken: null,
    user: null,
    isAuthenticated: false,
  });

  vi.spyOn(api, 'getAuthHeaders').mockResolvedValue({});
  vi.spyOn(api, 'listPatientAccessRequests').mockResolvedValue([]);
  vi.spyOn(globalThis, 'fetch').mockImplementation(
    async (input: RequestInfo | URL) => {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url.includes('/api/v1/dependents')) {
        return jsonResponse([]);
      }
      if (url.includes('/api/v1/profile')) {
        return jsonResponse({ id: 1, full_name: 'Test User' });
      }
      return new Response(null, { status: 404 });
    },
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

it('shows patient login and clinician portal actions when not authenticated', () => {
  render(<TopBar />);
  expect(screen.getByText('Patient Log In')).toBeInTheDocument();
  expect(screen.getByText('Clinician Portal')).toBeInTheDocument();
});

it('shows user name and logout when authenticated', async () => {
  useAppStore.setState({
    isAuthenticated: true,
    user: { id: 1, email: 'test@example.com', full_name: 'Test User', is_active: true },
  });
  render(<TopBar />);
  const user = userEvent.setup();
  // User avatar shows first letter of name
  expect(screen.getByText('T')).toBeInTheDocument();
  // Click menu to reveal user dropdown
  await user.click(screen.getByTestId('user-menu'));
  expect(screen.getByText('Test User')).toBeInTheDocument();
  expect(screen.getByText('Log Out')).toBeInTheDocument();
});
