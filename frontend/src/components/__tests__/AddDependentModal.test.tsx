import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as apiModule from '../../api';
import AddDependentModal from '../AddDependentModal';

describe('AddDependentModal', () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, 'createDependent').mockResolvedValue({
      id: 44,
      full_name: 'Jamie Doe',
      relationship_type: 'child',
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  it('shows required-field and guardian confirmation validation', async () => {
    render(<AddDependentModal isOpen onClose={vi.fn()} onAdded={vi.fn()} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Add Family Member' }));

    expect(screen.getByText('Please fill in all required fields')).toBeInTheDocument();
    expect(apiModule.api.createDependent).not.toHaveBeenCalled();

    await user.type(screen.getByPlaceholderText('Enter first name'), 'Jamie');
    await user.type(screen.getByPlaceholderText('Enter last name'), 'Doe');
    await user.type(screen.getByDisplayValue(''), '2020-05-10');
    await user.click(screen.getByRole('button', { name: 'Add Family Member' }));

    expect(
      screen.getByText('Please confirm you have permission to manage this record.'),
    ).toBeInTheDocument();
    expect(apiModule.api.createDependent).not.toHaveBeenCalled();
  });

  it('submits a dependent and resets state after close', async () => {
    const onAdded = vi.fn();
    const onClose = vi.fn();
    const { container, rerender } = render(
      <AddDependentModal
        isOpen
        onClose={onClose}
        onAdded={onAdded}
      />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /Spouse/ }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.type(screen.getByPlaceholderText('Enter first name'), 'Jamie');
    await user.type(screen.getByPlaceholderText('Enter last name'), 'Doe');
    await user.type(container.querySelector('input[type="date"]')!, '2020-05-10');
    const [sexSelect, bloodTypeSelect] = screen.getAllByRole('combobox');
    await user.selectOptions(sexSelect, 'female');
    await user.selectOptions(bloodTypeSelect, 'O+');
    await user.click(
      screen.getByLabelText(
        'I confirm I have permission to manage this person’s health records.',
      ),
    );
    await user.click(screen.getByRole('button', { name: 'Add Family Member' }));

    await waitFor(() => {
      expect(apiModule.api.createDependent).toHaveBeenCalledWith({
        first_name: 'Jamie',
        last_name: 'Doe',
        date_of_birth: '2020-05-10',
        relationship_type: 'spouse',
        sex: 'female',
        blood_type: 'O+',
      });
    });
    expect(onAdded).toHaveBeenCalledWith(44, 'Jamie Doe');
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(<AddDependentModal isOpen={false} onClose={onClose} onAdded={onAdded} />);
    rerender(<AddDependentModal isOpen onClose={onClose} onAdded={onAdded} />);

    expect(screen.getByText('Who would you like to add?')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Enter first name')).not.toBeInTheDocument();
  });
});
