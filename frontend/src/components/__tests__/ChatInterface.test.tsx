import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ChatInterface from '../ChatInterface';

beforeEach(() => {
  const speak = vi.fn();
  const cancel = vi.fn();
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      speak,
      cancel,
    },
  });
  class MockSpeechSynthesisUtterance {
    text: string;
    lang = '';
    rate = 1;
    onend: (() => void) | null = null;
    onerror: (() => void) | null = null;

    constructor(text: string) {
      this.text = text;
    }
  }
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: MockSpeechSynthesisUtterance,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

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

it('renders Apple Health structured summary cards for assistant messages', () => {
  render(
    <ChatInterface
      messages={[
        {
          role: 'assistant',
          content: 'Here is your Apple Health summary.',
          structured_data: {
            overview: 'Apple Health logged 10,322 steps from 2026-03-04 to 2026-03-10.',
            key_results: [
              { name: 'Total steps', value: '10,322', unit: 'steps' },
              { name: 'Average daily steps', value: '1,720', unit: 'steps/day' },
            ],
            what_changed: ['Daily steps decreased by 4,200 between 2026-03-04 and 2026-03-10.'],
            why_it_matters: ['This summary is based on 6 day(s) with synced step totals.'],
            section_sources: {
              key_results: ['apple_health#107'],
              what_changed: ['apple_health#102'],
            },
          },
        },
      ]}
      question=""
      isStreaming={false}
      onQuestionChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByText('Overview')).toBeInTheDocument();
  expect(screen.getByText('Key Results')).toBeInTheDocument();
  expect(screen.getByText('Total steps: 10,322 steps')).toBeInTheDocument();
  expect(screen.getByText('What Changed')).toBeInTheDocument();
  expect(screen.getByText('Daily steps decreased by 4,200 between 2026-03-04 and 2026-03-10.')).toBeInTheDocument();
  expect(screen.getByText('apple_health#107')).toBeInTheDocument();
});

it('shows language controls and plays an assistant reply aloud', async () => {
  const user = userEvent.setup();

  render(
    <ChatInterface
      messages={[
        {
          role: 'assistant',
          content: 'Hello! This is your health update.',
          output_language: 'en',
          speech_locale: 'en-US',
        },
      ]}
      question=""
      isStreaming={false}
      selectedLanguage="en"
      speechEnabled={false}
      onSpeechEnabledChange={vi.fn()}
      onLanguageChange={vi.fn()}
      onQuestionChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByTestId('chat-language-select')).toHaveValue('en');

  await user.click(screen.getByTestId('message-speak-button'));

  expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Stop audio')).toBeInTheDocument();
});
