import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  clearTranscript,
  playSpeechAsset,
  setTranscriptDraft,
  startRecording,
  stopRecordingAndTranscribe,
  synthesizeSpeech,
} = vi.hoisted(() => ({
  clearTranscript: vi.fn(),
  playSpeechAsset: vi.fn(),
  setTranscriptDraft: vi.fn(),
  startRecording: vi.fn(),
  stopRecordingAndTranscribe: vi.fn(),
  synthesizeSpeech: vi.fn(),
}));

vi.mock('../../hooks/useSpeech', () => ({
  default: () => ({
    isRecording: false,
    isUploading: false,
    isSynthesizing: false,
    audioPlaybackSupported: true,
    playingAudioAssetId: null,
    recordingSupported: true,
    recordingDurationMs: null,
    transcriptDraft: 'Hello from voice',
    setTranscriptDraft,
    transcriptConfidence: 0.92,
    lastTranscription: null,
    lastSynthesis: null,
    clearTranscript,
    resetSpeechState: vi.fn(),
    startRecording,
    stopRecordingAndTranscribe,
    cancelRecording: vi.fn(),
    transcribeAudio: vi.fn(),
    synthesizeSpeech,
    synthesizeAndPlaySpeech: vi.fn(),
    playSpeechAsset,
    stopPlayback: vi.fn(),
  }),
}));

import ChatInterface from '../ChatInterface';

beforeEach(() => {
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      speak: vi.fn(),
      cancel: vi.fn(),
    },
  });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: class MockSpeechSynthesisUtterance {
      text: string;

      constructor(text: string) {
        this.text = text;
      }
    },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe('ChatInterface voice flow', () => {
  it('synthesizes and plays a Swahili reply through the backend speech service', async () => {
    const user = userEvent.setup();
    synthesizeSpeech.mockResolvedValue({
      audio_asset_id: 'speech/sw/test.wav',
      output_language: 'sw',
      response_mode: 'speech',
      audio_url: '/api/v1/speech/assets/speech/sw/test.wav',
      audio_duration_ms: 980,
      speech_locale: 'sw-KE',
      model_name: 'facebook/mms-tts-swh',
    });

    render(
      <ChatInterface
        messages={[
          {
            role: 'assistant',
            content: 'Habari! Haya ni majibu yako.',
            output_language: 'sw',
          },
        ]}
        question=""
        isStreaming={false}
        selectedLanguage="sw"
        selectedPatient={{ id: 11, full_name: 'Demo User' }}
        onQuestionChange={vi.fn()}
        onSend={vi.fn()}
      />,
    );

    await user.click(screen.getByTestId('message-speak-button'));

    expect(synthesizeSpeech).toHaveBeenCalledWith(
      'Habari! Haya ni majibu yako.',
      expect.objectContaining({
        patientId: 11,
        outputLanguage: 'sw',
        responseMode: 'speech',
      }),
    );
    expect(playSpeechAsset).toHaveBeenCalledWith('speech/sw/test.wav');
  });

  it('shows transcript review and submits voice transcript explicitly', async () => {
    const user = userEvent.setup();
    const onVoiceSubmit = vi.fn();

    render(
      <ChatInterface
        messages={[]}
        question=""
        isStreaming={false}
        selectedLanguage="en"
        selectedPatient={{ id: 11, full_name: 'Demo User' }}
        voiceInputEnabled
        onVoiceSubmit={onVoiceSubmit}
        onQuestionChange={vi.fn()}
        onSend={vi.fn()}
      />,
    );

    expect(screen.getByTestId('chat-voice-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('chat-transcript-review')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Hello from voice')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Send transcript' }));

    expect(onVoiceSubmit).toHaveBeenCalledWith('Hello from voice');
    expect(clearTranscript).toHaveBeenCalledTimes(1);
  });
});
