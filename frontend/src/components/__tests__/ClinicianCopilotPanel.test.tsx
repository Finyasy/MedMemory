import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import { api } from '../../api';
import type { ClinicianAgentRun } from '../../types';
import ClinicianCopilotPanel from '../clinician/ClinicianCopilotPanel';

const runFixture: ClinicianAgentRun = {
  id: 42,
  patient_id: 7,
  clinician_user_id: 12,
  template: 'chart_review',
  prompt: 'Review this chart and surface the most important evidence for a clinician handoff.',
  status: 'completed',
  final_answer: 'Chart review completed.\nNot in documents.',
  citations: [
    {
      source_type: 'document',
      source_id: 5,
      label: 'Discharge note',
      detail: 'summary',
    },
  ],
  safety_flags: ['missing_documents'],
  steps: [
    {
      id: 1,
      step_order: 1,
      tool_name: 'patient_snapshot',
      title: 'Patient snapshot',
      status: 'completed',
      output_summary: '7 documents, 3 records.',
      citations: [],
      safety_flags: [],
      output_payload: null,
      created_at: '2026-03-07T10:30:00Z',
    },
  ],
  suggestions: [
    {
      id: 1,
      suggestion_order: 1,
      kind: 'request_more_documents',
      title: 'Request additional source documents',
      description: 'There are no uploaded documents for this patient.',
      action_label: 'Request uploads',
      action_target: 'patient:7:documents',
      citations: [],
      created_at: '2026-03-07T10:31:00Z',
    },
  ],
  error_message: null,
  created_at: '2026-03-07T10:30:00Z',
  completed_at: '2026-03-07T10:31:00Z',
};

beforeEach(() => {
  vi.spyOn(api, 'listClinicianAgentRuns').mockResolvedValue([]);
  vi.spyOn(api, 'getClinicianAgentRun').mockResolvedValue(runFixture);
  vi.spyOn(api, 'createClinicianAgentRun').mockResolvedValue(runFixture);
});

afterEach(() => {
  vi.restoreAllMocks();
});

it('runs a preset clinician copilot workflow and switches between latest run, history, and trace views', async () => {
  const user = userEvent.setup();
  const onNavigate = vi.fn();

  render(
    <ClinicianCopilotPanel
      patientId={7}
      patientName="Jane Doe"
      onError={vi.fn()}
      onNavigate={onNavigate}
      pushToast={vi.fn()}
    />,
  );

  expect(screen.getByText('Clinician Copilot')).toBeInTheDocument();
  expect(screen.getByText('Select a patient task above to generate a bounded copilot run.')).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Trace' })).toBeDisabled();

  await user.click(screen.getByRole('button', { name: 'Run Chart review' }));

  await waitFor(() => {
    expect(api.createClinicianAgentRun).toHaveBeenCalledWith({
      patient_id: 7,
      prompt: 'Review this chart and surface the most important evidence for a clinician handoff.',
      template: 'chart_review',
    });
  });

  expect(await screen.findByRole('tab', { name: 'Latest run' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'History' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Trace' })).toBeInTheDocument();
  expect(screen.getByText(/Chart review completed\./)).toBeInTheDocument();
  expect(screen.getByText('missing documents')).toBeInTheDocument();
  expect(screen.getByText('Citations')).toBeInTheDocument();
  expect(screen.getByText('Discharge note: summary')).toBeInTheDocument();
  expect(screen.getByText('Request additional source documents')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Request uploads' }));
  expect(onNavigate).toHaveBeenCalledWith('patient:7:documents');

  await user.click(screen.getByRole('tab', { name: 'Trace' }));
  expect(screen.getByText('Run trace')).toBeInTheDocument();
  expect(screen.getByText('1. Patient snapshot')).toBeInTheDocument();

  await user.click(screen.getByRole('tab', { name: 'History' }));
  expect(screen.getByText('Recent runs')).toBeInTheDocument();
  expect(screen.getByText('Review this chart and surface the most important evidence for a clinician handoff.')).toBeInTheDocument();
});
