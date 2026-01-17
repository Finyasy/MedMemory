import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it } from 'vitest';
import TopBar from '../TopBar';
import useAppStore from '../../store/useAppStore';

beforeEach(() => {
  useAppStore.setState({ 
    patientId: 1, 
    patientSearch: '', 
    apiKey: '',
    accessToken: null,
    user: null,
    isAuthenticated: false,
  });
});

afterEach(() => {
  cleanup();
});

it('shows login and signup buttons when not authenticated', () => {
  render(<TopBar />);
  expect(screen.getByText('Log In')).toBeInTheDocument();
  expect(screen.getByText('Sign Up')).toBeInTheDocument();
});

it('shows user name and logout when authenticated', () => {
  useAppStore.setState({
    isAuthenticated: true,
    user: { id: 1, email: 'test@example.com', full_name: 'Test User', is_active: true },
  });
  render(<TopBar />);
  expect(screen.getByText('Test User')).toBeInTheDocument();
  expect(screen.getByText('Log Out')).toBeInTheDocument();
});
