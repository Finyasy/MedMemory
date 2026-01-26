import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import ChatPanel from '../ChatPanel';

it('renders messages and calls send handler', () => {
  const handleSend = vi.fn();
  const handleChange = vi.fn();

  render(
    <ChatPanel
      messages={[{ role: 'assistant', content: 'Hello' }]}
      question=""
      isStreaming={false}
      onQuestionChange={handleChange}
      onSend={handleSend}
    />
  );

  expect(screen.getByText('Hello')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Send'));
  expect(handleSend).toHaveBeenCalledTimes(1);
});

it('shows tooltip data for upload', () => {
  render(
    <ChatPanel
      messages={[]}
      question=""
      isStreaming={false}
      onQuestionChange={vi.fn()}
      onSend={vi.fn()}
    />
  );

  const uploadLabels = screen.getAllByText('Add report');
  expect(uploadLabels[0]).toHaveAttribute(
    'data-tooltip',
    'Upload image(s), document, CT/MRI volume (.nii/.zip), WSI patches, or a CXR',
  );
});
