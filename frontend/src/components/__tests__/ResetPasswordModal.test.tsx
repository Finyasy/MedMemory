import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as apiModule from '../../api';
import ResetPasswordModal from '../ResetPasswordModal';

describe('ResetPasswordModal', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    vi.spyOn(apiModule.api, 'resetPassword').mockResolvedValue({ message: 'ok' });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('prefills the initial token and clears the reset-password route', () => {
    const replaceState = vi.spyOn(window.history, 'replaceState');
    window.history.pushState({}, '', '/reset-password?token=abc123');

    render(
      <ResetPasswordModal
        isOpen
        onClose={vi.fn()}
        initialToken="abc123"
      />,
    );

    expect(screen.queryByLabelText('Reset token')).not.toBeInTheDocument();
    expect(screen.getByText('Choose a new password for your account.')).toBeInTheDocument();
    expect(replaceState).toHaveBeenCalledWith({}, '', '/');
  });

  it('validates password length and password match before submission', async () => {
    render(<ResetPasswordModal isOpen onClose={vi.fn()} />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Reset token'), 'token-123');
    await user.type(screen.getByLabelText('New password'), 'short');
    await user.type(screen.getByLabelText('Confirm password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(screen.getByText('Password must be at least 8 characters long.')).toBeInTheDocument();
    expect(apiModule.api.resetPassword).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText('New password'));
    await user.clear(screen.getByLabelText('Confirm password'));
    await user.type(screen.getByLabelText('New password'), 'strong-pass');
    await user.type(screen.getByLabelText('Confirm password'), 'wrong-pass');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
    expect(apiModule.api.resetPassword).not.toHaveBeenCalled();
  });

  it('submits successfully and routes back to login', async () => {
    const onClose = vi.fn();
    const onBackToLogin = vi.fn();
    render(
      <ResetPasswordModal
        isOpen
        onClose={onClose}
        onBackToLogin={onBackToLogin}
      />,
    );
    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Reset token'), 'token-456');
    await user.type(screen.getByLabelText('New password'), 'strong-pass');
    await user.type(screen.getByLabelText('Confirm password'), 'strong-pass');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(await screen.findByText('Password updated')).toBeInTheDocument();
    expect(apiModule.api.resetPassword).toHaveBeenCalledWith('token-456', 'strong-pass');

    await user.click(screen.getByRole('button', { name: 'Back to login' }));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(onBackToLogin).toHaveBeenCalledTimes(1);
    });
  });
});
