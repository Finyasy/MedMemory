import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const { speechFetchAudioAsset, speechTranscribe, speechSynthesize } = vi.hoisted(() => ({
  speechFetchAudioAsset: vi.fn(),
  speechTranscribe: vi.fn(),
  speechSynthesize: vi.fn(),
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
      speechFetchAudioAsset,
      speechTranscribe,
      speechSynthesize,
    },
  };
});

import useSpeech from '../useSpeech';

describe('useSpeech', () => {
  it('stores transcription output for transcript review', async () => {
    speechTranscribe.mockResolvedValue({
      transcript: 'Hello from speech',
      detected_language: 'en',
      input_mode: 'voice',
      transcript_confidence: 0.91,
      duration_ms: 1100,
      model_name: 'google/medasr',
    });

    const onError = vi.fn();
    const file = new File(['audio'], 'clip.wav', { type: 'audio/wav' });
    const { result } = renderHook(() => useSpeech({ onError }));

    await act(async () => {
      await result.current.transcribeAudio(file, { language: 'en' });
    });

    expect(result.current.transcriptDraft).toBe('Hello from speech');
    expect(result.current.transcriptConfidence).toBe(0.91);
    expect(onError).not.toHaveBeenCalled();
  });

  it('stores synthesized speech asset metadata', async () => {
    speechSynthesize.mockResolvedValue({
      audio_asset_id: 'speech/sw/test.wav',
      output_language: 'sw',
      response_mode: 'speech',
      audio_url: '/audio/speech/sw/test.wav',
      audio_duration_ms: 980,
      speech_locale: 'sw-KE',
      model_name: 'facebook/mms-tts-swh',
    });

    const onError = vi.fn();
    const { result } = renderHook(() => useSpeech({ onError }));

    await act(async () => {
      await result.current.synthesizeSpeech('Habari yako?', { outputLanguage: 'sw' });
    });

    expect(result.current.lastSynthesis?.audio_asset_id).toBe('speech/sw/test.wav');
    expect(result.current.isSynthesizing).toBe(false);
    expect(onError).not.toHaveBeenCalled();
  });

  it('plays a fetched speech asset', async () => {
    const play = vi.fn().mockResolvedValue(undefined);
    const pause = vi.fn();
    speechFetchAudioAsset.mockResolvedValue(new Blob(['audio'], { type: 'audio/wav' }));
    class MockAudio {
      play = play;
      pause = pause;
      currentTime = 0;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(_src: string) {
        void _src;
      }
    }
    vi.stubGlobal('Audio', MockAudio);
    vi.stubGlobal(
      'URL',
      Object.assign(URL, {
        createObjectURL: vi.fn(() => 'blob:medmemory-audio'),
        revokeObjectURL: vi.fn(),
      }),
    );

    const onError = vi.fn();
    const { result } = renderHook(() => useSpeech({ onError }));

    await act(async () => {
      await result.current.playSpeechAsset('speech/sw/test.wav');
    });

    expect(speechFetchAudioAsset).toHaveBeenCalledWith('speech/sw/test.wav');
    expect(play).toHaveBeenCalledTimes(1);
    expect(result.current.playingAudioAssetId).toBe('speech/sw/test.wav');
    expect(onError).not.toHaveBeenCalled();
  });
});
