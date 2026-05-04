import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { streamChat, chatAsk, getConversation } = vi.hoisted(() => ({
  streamChat: vi.fn(),
  chatAsk: vi.fn(),
  getConversation: vi.fn(),
}));

vi.mock('../../api', () => {
  class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }

  return {
    ApiError,
    api: {
      streamChat,
      chatAsk,
      getConversation,
    },
  };
});

import useChat from '../useChat';

describe('useChat', () => {
  beforeEach(() => {
    streamChat.mockReset();
    chatAsk.mockReset();
    getConversation.mockReset();
    window.localStorage.clear();
  });

  it('sends voice transcripts through the normal chat flow with input_mode=voice', async () => {
    streamChat.mockImplementation(
      async (
        _patientId: number,
        _prompt: string,
        onChunk: (chunk: string) => void,
        onDone: () => void,
        options?: { inputMode?: string; onMetadata?: (metadata: Record<string, unknown>) => void },
      ) => {
        options?.onMetadata?.({
          input_mode: options?.inputMode,
          response_mode: 'text',
          output_language: 'en',
        });
        onChunk('Voice answer');
        onDone();
      },
    );

    const onError = vi.fn();
    const { result } = renderHook(() => useChat({ patientId: 1, onError, language: 'en' }));

    await act(async () => {
      await result.current.sendVoiceTranscript('What are my recent labs?');
    });

    expect(streamChat).toHaveBeenCalledWith(
      1,
      'What are my recent labs?',
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ inputMode: 'voice' }),
    );
    expect(result.current.messages.some((message) => message.input_mode === 'voice')).toBe(true);
    expect(onError).not.toHaveBeenCalled();
  });

  it('routes Apple Health prompts through the coaching path and preserves structured data', async () => {
    chatAsk.mockResolvedValue({
      answer: 'Here is your Apple Health summary.',
      conversation_id: 'conv-apple-health',
      structured_data: {
        overview: 'Apple Health logged 10,322 steps from 2026-03-04 to 2026-03-10.',
        key_results: [
          { name: 'Total steps', value: '10,322', unit: 'steps' },
        ],
      },
      sources: [{ source_type: 'apple_health', source_id: 107, relevance: 0.79 }],
      num_sources: 1,
      input_mode: 'text',
      response_mode: 'text',
      output_language: 'en',
    });

    const onError = vi.fn();
    const { result } = renderHook(() => useChat({ patientId: 1, onError, language: 'en' }));

    await act(async () => {
      result.current.setQuestion('Any Apple Health info across one week?');
    });

    await act(async () => {
      await result.current.send();
    });

    expect(chatAsk).toHaveBeenCalledWith(
      1,
      'Any Apple Health info across one week?',
      expect.objectContaining({
        structured: true,
        coachingMode: true,
        input_language: 'en',
        output_language: 'en',
      }),
    );
    expect(result.current.messages.at(-1)?.structured_data).toEqual(
      expect.objectContaining({
        overview: 'Apple Health logged 10,322 steps from 2026-03-04 to 2026-03-10.',
      }),
    );
    expect(
      window.localStorage.getItem('medmemory:conversation:patient:1'),
    ).toBe('conv-apple-health');
    expect(onError).not.toHaveBeenCalled();
  });

  it('rehydrates the last stored conversation with structured cards on mount', async () => {
    window.localStorage.setItem('medmemory:conversation:patient:1', 'conv-existing');
    getConversation.mockResolvedValue({
      conversation_id: 'conv-existing',
      patient_id: 1,
      title: 'Check-in',
      created_at: '2026-03-11T10:00:00Z',
      updated_at: '2026-03-11T10:01:00Z',
      message_count: 2,
      messages: [
        {
          role: 'user',
          content: 'Any Apple Health info across one week?',
          timestamp: '2026-03-11T10:00:10Z',
          message_id: 10,
          structured_data: null,
        },
        {
          role: 'assistant',
          content: 'Here is your Apple Health summary.',
          timestamp: '2026-03-11T10:00:12Z',
          message_id: 11,
          structured_data: {
            overview: 'Apple Health logged 10,322 steps from 2026-03-04 to 2026-03-10.',
          },
        },
      ],
    });

    const onError = vi.fn();
    const { result } = renderHook(() => useChat({ patientId: 1, onError, language: 'en' }));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    expect(getConversation).toHaveBeenCalledWith('conv-existing');
    expect(result.current.messages[1]?.structured_data).toEqual(
      expect.objectContaining({
        overview: 'Apple Health logged 10,322 steps from 2026-03-04 to 2026-03-10.',
      }),
    );
    expect(onError).not.toHaveBeenCalled();
  });
});
