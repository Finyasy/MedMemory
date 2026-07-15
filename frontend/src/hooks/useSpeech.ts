import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, api } from '../api';
import type {
  ChatResponseMode,
  SpeechSynthesisResult,
  SpeechTranscriptionResult,
} from '../types';

type UseSpeechOptions = {
  onError: (label: string, error: unknown) => void;
};

type TranscribeAudioOptions = {
  patientId?: number;
  clinicianMode?: boolean;
  language?: string;
};

type SynthesizeSpeechOptions = {
  patientId?: number;
  conversationId?: string;
  messageId?: number;
  outputLanguage?: string;
  responseMode?: Extract<ChatResponseMode, 'speech' | 'both'>;
};

const AUDIO_MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/ogg',
] as const;

const pickRecordingMimeType = (): string | null => {
  if (typeof window === 'undefined' || typeof window.MediaRecorder === 'undefined') {
    return null;
  }
  const { MediaRecorder } = window;
  if (typeof MediaRecorder.isTypeSupported !== 'function') {
    return AUDIO_MIME_CANDIDATES[0];
  }
  return (
    AUDIO_MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? null
  );
};

const fileExtensionForMimeType = (mimeType: string | null | undefined): string => {
  if (!mimeType) return 'webm';
  if (mimeType.includes('ogg')) return 'ogg';
  if (mimeType.includes('mp4')) return 'm4a';
  if (mimeType.includes('wav')) return 'wav';
  return 'webm';
};

const useSpeech = ({ onError }: UseSpeechOptions) => {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number | null>(null);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  const assetUrlCacheRef = useRef<Map<string, string>>(new Map());

  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [playingAudioAssetId, setPlayingAudioAssetId] = useState<string | null>(null);
  const [recordingDurationMs, setRecordingDurationMs] = useState<number | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const [transcriptConfidence, setTranscriptConfidence] = useState<number | null>(null);
  const [lastTranscription, setLastTranscription] = useState<SpeechTranscriptionResult | null>(null);
  const [lastSynthesis, setLastSynthesis] = useState<SpeechSynthesisResult | null>(null);

  const recordingSupported = useMemo(
    () =>
      typeof navigator !== 'undefined' &&
      Boolean(navigator.mediaDevices?.getUserMedia) &&
      typeof window !== 'undefined' &&
      typeof window.MediaRecorder !== 'undefined',
    [],
  );
  const audioPlaybackSupported = useMemo(() => typeof Audio !== 'undefined', []);

  const releaseMediaResources = useCallback(() => {
    mediaRecorderRef.current = null;
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    audioChunksRef.current = [];
    recordingStartedAtRef.current = null;
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscriptDraft('');
    setTranscriptConfidence(null);
    setLastTranscription(null);
    setRecordingDurationMs(null);
  }, []);

  const resetSpeechState = useCallback(() => {
    setIsRecording(false);
    setIsUploading(false);
    setIsSynthesizing(false);
    setPlayingAudioAssetId(null);
    setLastSynthesis(null);
    releaseMediaResources();
    clearTranscript();
  }, [clearTranscript, releaseMediaResources]);

  const stopPlayback = useCallback(() => {
    const currentPlayback = playbackRef.current;
    if (currentPlayback) {
      currentPlayback.pause();
      currentPlayback.currentTime = 0;
      playbackRef.current = null;
    }
    setPlayingAudioAssetId(null);
  }, []);

  const getAssetObjectUrl = useCallback(async (assetId: string) => {
    const cachedUrl = assetUrlCacheRef.current.get(assetId);
    if (cachedUrl) return cachedUrl;
    const blob = await api.speechFetchAudioAsset(assetId);
    const objectUrl = URL.createObjectURL(blob);
    assetUrlCacheRef.current.set(assetId, objectUrl);
    return objectUrl;
  }, []);

  const transcribeAudio = useCallback(
    async (audio: File, options?: TranscribeAudioOptions) => {
      setIsUploading(true);
      try {
        const result = await api.speechTranscribe(audio, options);
        setTranscriptDraft(result.transcript);
        setTranscriptConfidence(
          typeof result.transcript_confidence === 'number' ? result.transcript_confidence : null,
        );
        setLastTranscription(result);
        return result;
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          onError('Speech auth failed', error);
        } else {
          onError('Speech transcription failed', error);
        }
        throw error;
      } finally {
        setIsUploading(false);
      }
    },
    [onError],
  );

  const startRecording = useCallback(async () => {
    if (!recordingSupported) {
      const error = new Error('Voice input is not available in this browser.');
      onError('Voice input unavailable', error);
      throw error;
    }

    clearTranscript();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickRecordingMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      audioChunksRef.current = [];
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        setIsRecording(false);
        onError('Voice recording failed', new Error('Audio recording failed.'));
        releaseMediaResources();
      };

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recordingStartedAtRef.current = Date.now();
      recorder.start();
      setIsRecording(true);
    } catch (error) {
      releaseMediaResources();
      onError('Microphone access failed', error);
      throw error;
    }
  }, [clearTranscript, onError, recordingSupported, releaseMediaResources]);

  const stopRecordingAndTranscribe = useCallback(
    async (options?: TranscribeAudioOptions) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder) return null;
      if (recorder.state === 'inactive') return null;

      setIsRecording(false);
      return await new Promise<SpeechTranscriptionResult | null>((resolve, reject) => {
        recorder.onstop = async () => {
          const recordedMimeType = recorder.mimeType || pickRecordingMimeType() || 'audio/webm';
          const audioBlob = new Blob(audioChunksRef.current, { type: recordedMimeType });
          const extension = fileExtensionForMimeType(recordedMimeType);
          const recordedAt = recordingStartedAtRef.current;
          const elapsed = recordedAt ? Math.max(Date.now() - recordedAt, 0) : null;
          setRecordingDurationMs(elapsed);
          releaseMediaResources();

          if (!audioBlob.size) {
            const error = new Error('Recorded audio was empty.');
            onError('Voice recording failed', error);
            reject(error);
            return;
          }

          try {
            const file = new File([audioBlob], `medmemory-voice.${extension}`, {
              type: recordedMimeType,
            });
            const result = await transcribeAudio(file, options);
            resolve(result);
          } catch (error) {
            reject(error);
          }
        };
        recorder.stop();
      });
    },
    [onError, releaseMediaResources, transcribeAudio],
  );

  const cancelRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      recorder.stop();
    }
    setIsRecording(false);
    releaseMediaResources();
  }, [releaseMediaResources]);

  const synthesizeSpeech = useCallback(
    async (text: string, options?: SynthesizeSpeechOptions) => {
      setIsSynthesizing(true);
      try {
        const result = await api.speechSynthesize({
          text,
          patient_id: options?.patientId,
          conversation_id: options?.conversationId,
          message_id: options?.messageId,
          output_language: options?.outputLanguage ?? 'sw',
          response_mode: options?.responseMode ?? 'speech',
        });
        setLastSynthesis(result);
        return result;
      } catch (error) {
        onError('Speech synthesis failed', error);
        throw error;
      } finally {
        setIsSynthesizing(false);
      }
    },
    [onError],
  );

  const playSpeechAsset = useCallback(
    async (assetId: string) => {
      if (!audioPlaybackSupported) {
        const error = new Error('Audio playback is not available in this browser.');
        onError('Speech playback unavailable', error);
        throw error;
      }
      if (playingAudioAssetId === assetId) {
        stopPlayback();
        return;
      }
      stopPlayback();
      try {
        const objectUrl = await getAssetObjectUrl(assetId);
        const playback = new Audio(objectUrl);
        playbackRef.current = playback;
        playback.onended = () => {
          playbackRef.current = null;
          setPlayingAudioAssetId((current) => (current === assetId ? null : current));
        };
        playback.onerror = () => {
          playbackRef.current = null;
          setPlayingAudioAssetId(null);
          onError('Speech playback failed', new Error('Unable to play generated speech.'));
        };
        setPlayingAudioAssetId(assetId);
        await playback.play();
      } catch (error) {
        playbackRef.current = null;
        setPlayingAudioAssetId(null);
        onError('Speech playback failed', error);
        throw error;
      }
    },
    [audioPlaybackSupported, getAssetObjectUrl, onError, playingAudioAssetId, stopPlayback],
  );

  const synthesizeAndPlaySpeech = useCallback(
    async (text: string, options?: SynthesizeSpeechOptions) => {
      const result = await synthesizeSpeech(text, options);
      await playSpeechAsset(result.audio_asset_id);
      return result;
    },
    [playSpeechAsset, synthesizeSpeech],
  );

  useEffect(() => () => {
    stopPlayback();
    assetUrlCacheRef.current.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    assetUrlCacheRef.current.clear();
    releaseMediaResources();
  }, [releaseMediaResources, stopPlayback]);

  return {
    isRecording,
    isUploading,
    isSynthesizing,
    audioPlaybackSupported,
    playingAudioAssetId,
    recordingSupported,
    recordingDurationMs,
    transcriptDraft,
    setTranscriptDraft,
    transcriptConfidence,
    lastTranscription,
    lastSynthesis,
    clearTranscript,
    resetSpeechState,
    startRecording,
    stopRecordingAndTranscribe,
    cancelRecording,
    transcribeAudio,
    synthesizeSpeech,
    synthesizeAndPlaySpeech,
    playSpeechAsset,
    stopPlayback,
  };
};

export default useSpeech;
