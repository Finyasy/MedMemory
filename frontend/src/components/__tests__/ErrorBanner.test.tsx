import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import ErrorBanner from '../ErrorBanner';

it('renders nothing when message is null', () => {
  const { container } = render(<ErrorBanner message={null} />);
  expect(container).toBeEmptyDOMElement();
});

it('renders message when provided', () => {
  render(<ErrorBanner message="Something broke" />);
  expect(screen.getByRole('alert')).toHaveTextContent('Something broke');
});
