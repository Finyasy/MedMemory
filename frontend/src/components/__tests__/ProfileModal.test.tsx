import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../api';
import ProfileModal from '../ProfileModal';

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const baseProfile = {
  id: 7,
  first_name: 'Alice',
  last_name: 'Bosire',
  full_name: 'Alice Bosire',
  date_of_birth: '2010-01-02',
  age: 16,
  sex: 'female',
  gender: 'female',
  blood_type: 'O+',
  height_cm: 160,
  weight_kg: 55,
  phone: '+254700000000',
  email: 'alice@example.com',
  address: 'Nairobi',
  preferred_language: 'sw',
  emergency_contacts: [],
  allergies: [],
  conditions: [],
  family_history: [],
  providers: [],
  lifestyle: null,
  profile_completion: { overall_percentage: 82 },
};

describe('ProfileModal', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getAuthHeaders').mockResolvedValue({ Authorization: 'Bearer token' });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  it('loads profile data and populates the basic info form', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse(baseProfile));

    render(<ProfileModal isOpen onClose={vi.fn()} patientId={7} />);

    expect(await screen.findByDisplayValue('Alice')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Bosire')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getAllByRole('combobox').at(-1)).toHaveValue('sw');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:3000/api/v1/profile?patient_id=7',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token',
          'Content-Type': 'application/json',
        }),
      }),
    );
  });

  it('saves basic changes and dispatches a profile-updated event', async () => {
    let currentProfile = { ...baseProfile };
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url.endsWith('/api/v1/profile?patient_id=7') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(currentProfile);
        }
        if (url.endsWith('/api/v1/profile/basic?patient_id=7') && init?.method === 'PUT') {
          const payload = JSON.parse(String(init.body));
          currentProfile = {
            ...currentProfile,
            ...payload,
            full_name: `${payload.first_name ?? currentProfile.first_name} ${payload.last_name ?? currentProfile.last_name}`,
          };
          return jsonResponse(currentProfile);
        }
        return jsonResponse({ detail: 'missing' }, 404);
      });

    const onUpdated = vi.fn();
    window.addEventListener(
      'medmemory:profile-updated',
      onUpdated as unknown as EventListener,
    );
    render(<ProfileModal isOpen onClose={vi.fn()} patientId={7} />);
    const user = userEvent.setup();

    const firstNameInput = await screen.findByDisplayValue('Alice');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'Alicia');
    await user.click(screen.getByText('Save Changes'));

    await waitFor(() => {
      expect(onUpdated).toHaveBeenCalledTimes(1);
    });

    const updateEvent = onUpdated.mock.calls[0]?.[0] as CustomEvent;
    expect(updateEvent.detail).toEqual({
      patientId: 7,
      preferredLanguage: 'sw',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:3000/api/v1/profile/basic?patient_id=7',
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"first_name":"Alicia"'),
      }),
    );

    window.removeEventListener(
      'medmemory:profile-updated',
      onUpdated as unknown as EventListener,
    );
  });

  it('shows the error state and can retry loading', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(
          { detail: 'No health profile found. Please create a patient record first.' },
          404,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(baseProfile));

    render(<ProfileModal isOpen onClose={vi.fn()} patientId={7} />);
    const user = userEvent.setup();

    expect(await screen.findByText('Unable to Load Profile')).toBeInTheDocument();
    await user.click(screen.getByText('Try Again'));

    expect(await screen.findByDisplayValue('Alice')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
