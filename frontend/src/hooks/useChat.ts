import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api } from '../api';
import useAppStore from '../store/useAppStore';
import type { ChatMessage, ChatResponseMode, ChatSource } from '../types';
import {
  getPatientStrings,
  normalizePatientLanguage,
  type SupportedPatientLanguage,
} from '../utils/patientLanguage';

type UseChatOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  clinicianMode?: boolean;
  language?: SupportedPatientLanguage;
  speechOutputEnabled?: boolean;
};

type SendMessageOptions = {
  inputMode?: 'text' | 'voice';
};

const buildInitialMessages = (language: SupportedPatientLanguage): ChatMessage[] => [
  {
    role: 'assistant',
    content: getPatientStrings(language).introPrompt,
    output_language: language,
  },
];

const conversationStorageKey = (patientId: number, clinicianMode: boolean) =>
  `medmemory:conversation:${clinicianMode ? 'clinician' : 'patient'}:${patientId}`;

const readStoredConversationId = (patientId: number, clinicianMode: boolean) => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(conversationStorageKey(patientId, clinicianMode));
};

const writeStoredConversationId = (
  patientId: number,
  clinicianMode: boolean,
  conversationId: string | null,
) => {
  if (typeof window === 'undefined') return;
  const key = conversationStorageKey(patientId, clinicianMode);
  if (conversationId) {
    window.localStorage.setItem(key, conversationId);
    return;
  }
  window.localStorage.removeItem(key);
};

const toConversationChatMessage = (
  message: {
    role: 'user' | 'assistant';
    content: string;
    message_id?: number | null;
    structured_data?: Record<string, unknown> | null;
  },
): ChatMessage => ({
  role: message.role,
  content: message.content,
  message_id: message.message_id ?? null,
  structured_data:
    message.structured_data && typeof message.structured_data === 'object'
      ? message.structured_data
      : null,
});

const useChat = ({
  patientId,
  onError,
  clinicianMode,
  language = 'en',
  speechOutputEnabled = false,
}: UseChatOptions) => {
  const resolvedLanguage = normalizePatientLanguage(language);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(() => buildInitialMessages(resolvedLanguage));
  const [isStreaming, setIsStreaming] = useState(false);
  const [isHydratingConversation, setIsHydratingConversation] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(() =>
    readStoredConversationId(patientId, Boolean(clinicianMode)),
  );
  const languageRef = useRef(resolvedLanguage);

  useEffect(() => {
    languageRef.current = resolvedLanguage;
  }, [resolvedLanguage]);

  useEffect(() => {
    let cancelled = false;
    const storedConversationId = readStoredConversationId(
      patientId,
      Boolean(clinicianMode),
    );
    setQuestion('');
    setIsStreaming(false);
    setConversationId(storedConversationId);

    if (!storedConversationId) {
      setIsHydratingConversation(false);
      setMessages(buildInitialMessages(languageRef.current));
      return () => {
        cancelled = true;
      };
    }

    setIsHydratingConversation(true);
    api.getConversation(storedConversationId)
      .then((conversation) => {
        if (cancelled) return;
        const hydratedMessages = Array.isArray(conversation.messages)
          ? conversation.messages.map((message) => toConversationChatMessage(message))
          : [];
        if (hydratedMessages.length === 0) {
          writeStoredConversationId(patientId, Boolean(clinicianMode), null);
          setConversationId(null);
          setMessages(buildInitialMessages(languageRef.current));
          return;
        }
        setConversationId(conversation.conversation_id);
        writeStoredConversationId(
          patientId,
          Boolean(clinicianMode),
          conversation.conversation_id,
        );
        setMessages(hydratedMessages);
      })
      .catch((error) => {
        if (cancelled) return;
        writeStoredConversationId(patientId, Boolean(clinicianMode), null);
        setConversationId(null);
        setMessages(buildInitialMessages(languageRef.current));
        if (!(error instanceof ApiError && error.status === 404)) {
          onError('Conversation reload failed', error);
        }
      })
      .finally(() => {
        if (!cancelled) setIsHydratingConversation(false);
      });

    return () => {
      cancelled = true;
    };
  }, [patientId, clinicianMode, onError]);

  useEffect(() => {
    setMessages((prev) => {
      if (
        prev.length === 1 &&
        prev[0]?.role === 'assistant'
      ) {
        return buildInitialMessages(resolvedLanguage);
      }
      return prev;
    });
  }, [resolvedLanguage]);

  const send = useCallback(async (promptOverride?: string, options?: SendMessageOptions) => {
    const prompt = promptOverride?.trim() || question.trim();
    if (!prompt || isStreaming || isHydratingConversation) return;
    const inputMode = options?.inputMode ?? 'text';
    const responseMode: ChatResponseMode =
      !clinicianMode && resolvedLanguage === 'sw' && speechOutputEnabled ? 'both' : 'text';
    const isSummaryPrompt = /most recent document|latest document|summarize|summary|overview|findings/i.test(prompt);
    const isCoachingPrompt = /how(?:'s|\s+is)\s+my|what changed|trend|reviewed .* levels|explain .* level|is this improving|apple health|daily steps|step count|steps?\s+(?:over|across|during|for|from|last|past)|activity\s+trend/i.test(prompt);
    const useStructuredPath = isSummaryPrompt || isCoachingPrompt;
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: prompt, input_mode: inputMode },
      { role: 'assistant', content: '' },
    ]);
    setIsStreaming(true);

    let accumulator = '';
    let streamMetadata: {
      conversation_id?: string;
      message_id?: number;
      input_mode?: 'text' | 'voice';
      response_mode?: ChatResponseMode;
      num_sources?: number;
      sources?: ChatSource[];
      structured_data?: Record<string, unknown> | null;
      detected_language?: string | null;
      input_language?: string | null;
      output_language?: string | null;
      translated_question?: string | null;
      translation_applied?: boolean;
      speech_locale?: string | null;
      audio_asset_id?: string | null;
      audio_url?: string | null;
      audio_duration_ms?: number | null;
      transcript_confidence?: number | null;
    } = {};
    try {
      if (useStructuredPath) {
        const response = await api.chatAsk(patientId, prompt, {
          conversation_id: conversationId,
          use_conversation_history: false,
          structured: true,
          coachingMode: isCoachingPrompt,
          clinicianMode: Boolean(clinicianMode),
          input_language: resolvedLanguage,
          output_language: resolvedLanguage,
          input_mode: inputMode,
          response_mode: responseMode,
        });
        const sources = Array.isArray(response.sources)
          ? (response.sources as ChatSource[])
          : [];
        const numSources = typeof response.num_sources === 'number'
          ? response.num_sources
          : sources.length;
        const structuredData = (
          response.structured_data &&
          typeof response.structured_data === 'object'
        )
          ? (response.structured_data as Record<string, unknown>)
          : null;
        const nextConversationId =
          typeof response.conversation_id === 'string'
            ? response.conversation_id
            : conversationId;
        setConversationId(nextConversationId ?? null);
        writeStoredConversationId(
          patientId,
          Boolean(clinicianMode),
          nextConversationId ?? null,
        );
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: response.answer,
            message_id: response.message_id ?? null,
            input_mode: response.input_mode ?? 'text',
            response_mode: response.response_mode ?? responseMode,
            sources,
            num_sources: numSources,
            structured_data: structuredData,
            detected_language: response.detected_language ?? null,
            input_language: response.input_language ?? null,
            output_language: response.output_language ?? resolvedLanguage,
            translated_question: response.translated_question ?? null,
            translation_applied: Boolean(response.translation_applied),
            speech_locale: response.speech_locale ?? null,
            audio_asset_id: response.audio_asset_id ?? null,
            audio_url: response.audio_url ?? null,
            audio_duration_ms:
              typeof response.audio_duration_ms === 'number' ? response.audio_duration_ms : null,
            transcript_confidence:
              typeof response.transcript_confidence === 'number'
                ? response.transcript_confidence
                : null,
          };
          return updated;
        });
        setIsStreaming(false);
        return;
      }

      await api.streamChat(
        patientId,
        prompt,
        (chunk) => {
          accumulator += chunk;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: 'assistant',
              content: accumulator,
              sources: streamMetadata.sources,
              num_sources: streamMetadata.num_sources,
              structured_data: streamMetadata.structured_data ?? null,
            };
            return updated;
          });
        },
        () => {
          setIsStreaming(false);
        },
        {
          conversationId: conversationId ?? undefined,
          clinicianMode,
          inputLanguage: resolvedLanguage,
          outputLanguage: resolvedLanguage,
          inputMode,
          responseMode,
          onMetadata: (metadata) => {
            const nextConversationId =
              typeof metadata.conversation_id === 'string'
                ? metadata.conversation_id
                : conversationId;
            setConversationId(nextConversationId ?? null);
            writeStoredConversationId(
              patientId,
              Boolean(clinicianMode),
              nextConversationId ?? null,
            );
            streamMetadata = {
              conversation_id: nextConversationId ?? undefined,
              message_id:
                typeof metadata.message_id === 'number' ? metadata.message_id : undefined,
              input_mode: metadata.input_mode ?? 'text',
              response_mode: metadata.response_mode ?? responseMode,
              num_sources: metadata.num_sources,
              sources: metadata.sources,
              structured_data: metadata.structured_data ?? null,
              detected_language: metadata.detected_language ?? null,
              input_language: metadata.input_language ?? null,
              output_language: metadata.output_language ?? resolvedLanguage,
              translated_question: metadata.translated_question ?? null,
              translation_applied: Boolean(metadata.translation_applied),
              speech_locale: metadata.speech_locale ?? null,
              audio_asset_id: metadata.audio_asset_id ?? null,
              audio_url: metadata.audio_url ?? null,
              audio_duration_ms:
                typeof metadata.audio_duration_ms === 'number' ? metadata.audio_duration_ms : null,
              transcript_confidence:
                typeof metadata.transcript_confidence === 'number'
                  ? metadata.transcript_confidence
                  : null,
            };
            setMessages((prev) => {
              const updated = [...prev];
              const currentContent = accumulator || updated[updated.length - 1]?.content || '';
              updated[updated.length - 1] = {
                role: 'assistant',
                content: currentContent,
                message_id: streamMetadata.message_id ?? null,
                input_mode: streamMetadata.input_mode,
                response_mode: streamMetadata.response_mode,
                sources: streamMetadata.sources,
                num_sources: streamMetadata.num_sources,
                structured_data: streamMetadata.structured_data,
                detected_language: streamMetadata.detected_language,
                input_language: streamMetadata.input_language,
                output_language: streamMetadata.output_language,
                translated_question: streamMetadata.translated_question,
                translation_applied: streamMetadata.translation_applied,
                speech_locale: streamMetadata.speech_locale,
                audio_asset_id: streamMetadata.audio_asset_id,
                audio_url: streamMetadata.audio_url,
                audio_duration_ms: streamMetadata.audio_duration_ms,
                transcript_confidence: streamMetadata.transcript_confidence,
              };
              return updated;
            });
          },
        },
      );
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        useAppStore.getState().setAccessToken(null);
      }
      onError('Chat failed', error);
      setIsStreaming(false);
    }
  }, [
    patientId,
    question,
    isStreaming,
    isHydratingConversation,
    onError,
    clinicianMode,
    resolvedLanguage,
    speechOutputEnabled,
    conversationId,
  ]);

  const sendVoiceTranscript = useCallback(
    async (transcript: string) => send(transcript, { inputMode: 'voice' }),
    [send],
  );

  const sendVision = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming || isHydratingConversation) return;
    const defaultPrompt = `Analyze this medical image or document. Be concise and focus on what is actually visible.

For medical images (X-rays, scans, photos):
- Identify the image type (e.g., "Chest X-ray", "MRI brain scan")
- Describe key anatomical structures and any visible findings
- Only report text, labels, or numbers that are clearly readable (not "partially visible")
- Do NOT invent measurements unless there is a visible scale or ruler
- Avoid repetitive descriptions - summarize similar findings

For documents with text:
- Extract all visible text, numbers, and values exactly as written
- Include units and labels
- If text is unclear, note that briefly

Be concise and focus on actual findings, not possibilities.`;
    const prompt = promptOverride?.trim() || defaultPrompt;
    // Show a clean user message (not the full prompt)
    const userDisplayMessage = promptOverride?.trim() 
      ? `${promptOverride.trim()}\n📎 ${file.name}`
      : `📎 Analyzing: ${file.name}`;
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userDisplayMessage },
      { role: 'assistant', content: '' },
    ]);
    setIsStreaming(true);

    try {
      const response = await api.visionChat(patientId, prompt, file);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: response.answer };
        return updated;
      });
    } catch (error) {
      onError('Vision chat failed', error);
      throw error;
    } finally {
      setIsStreaming(false);
    }
  }, [patientId, isStreaming, isHydratingConversation, onError]);

  const pushMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  const sendVolume = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming || isHydratingConversation) return;
    const prompt = promptOverride?.trim() || 'Summarize findings from this CT/MRI volume.';
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: `${prompt}\n[Volume: ${file.name}]` },
      { role: 'assistant', content: '' },
    ]);
    setIsStreaming(true);

    try {
      const response = await api.volumeChat(patientId, prompt, file, { modality: 'CT/MRI' });
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: response.answer };
        return updated;
      });
    } catch (error) {
      onError('Volume analysis failed', error);
      throw error;
    } finally {
      setIsStreaming(false);
    }
  }, [patientId, isStreaming, isHydratingConversation, onError]);

  const sendWsi = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming || isHydratingConversation) return;
    const prompt = promptOverride?.trim() || 'Summarize histopathology patches.';
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: `${prompt}\n[WSI patches: ${file.name}]` },
      { role: 'assistant', content: '' },
    ]);
    setIsStreaming(true);

    try {
      const response = await api.wsiChat(patientId, prompt, file);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: response.answer };
        return updated;
      });
    } catch (error) {
      onError('WSI analysis failed', error);
      throw error;
    } finally {
      setIsStreaming(false);
    }
  }, [patientId, isStreaming, isHydratingConversation, onError]);

  const sendCxrCompare = useCallback(async (currentFile: File, priorFile: File, promptOverride?: string) => {
    if (isStreaming || isHydratingConversation) return;
    const prompt = promptOverride?.trim() || 'Compare these chest X-rays and summarize changes.';
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: `${prompt}\n[Baseline/Prior: ${priorFile.name}, Current/Follow-up: ${currentFile.name}]`,
      },
      { role: 'assistant', content: '' },
    ]);
    setIsStreaming(true);

    try {
      const response = await api.compareCxr(patientId, prompt, currentFile, priorFile);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: response.answer };
        return updated;
      });
    } catch (error) {
      onError('CXR comparison failed', error);
      throw error;
    } finally {
      setIsStreaming(false);
    }
  }, [patientId, isStreaming, isHydratingConversation, onError]);

  return {
    messages,
    question,
    setQuestion,
    isStreaming: isStreaming || isHydratingConversation,
    send,
    sendVoiceTranscript,
    sendVision,
    sendVolume,
    sendWsi,
    sendCxrCompare,
    pushMessage,
  };
};

export default useChat;
