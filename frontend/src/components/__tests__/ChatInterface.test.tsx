import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import ChatInterface from '../ChatInterface';

it('renders guardrail badges for assistant messages', () => {
  render(
    <ChatInterface
      messages={[
        {
          role: 'assistant',
          content: 'From your records: HbA1c is 7.1% (source: lab_result#12).',
          sources: [{ source_type: 'lab_result', source_id: 12, relevance: 0.82 }],
          structured_data: { overview: 'HbA1c result summary' },
        },
      ]}
      question=""
      isStreaming={false}
      onQuestionChange={vi.fn()}
      onSend={vi.fn()}
    />
  );

  expect(screen.getByText('Grounded')).toBeInTheDocument();
  expect(screen.getByText('Structured')).toBeInTheDocument();
  expect(screen.getByText('Cited')).toBeInTheDocument();
  expect(screen.getByText('Record-Based')).toBeInTheDocument();
});
