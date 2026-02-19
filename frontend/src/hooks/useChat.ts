import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import useAppStore from '../store/useAppStore';
import type { ChatMessage, ChatSource } from '../types';

type UseChatOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
  clinicianMode?: boolean;
};

const initialMessages: ChatMessage[] = [
  {
    role: 'assistant',
    content:
      'Ask about a specific report, lab value, medication, or date. I will only use what is in the record.',
  },
];

const useChat = ({ patientId, onError, clinicianMode }: UseChatOptions) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    setMessages(initialMessages);
    setQuestion('');
    setIsStreaming(false);
  }, [patientId]);

  const send = useCallback(async (promptOverride?: string) => {
    const prompt = promptOverride?.trim() || question.trim();
    if (!prompt || isStreaming) return;
    const isSummaryPrompt = /most recent document|latest document|summarize|summary|overview|findings/i.test(prompt);
    const isCoachingPrompt = /how(?:'s|\s+is)\s+my|what changed|trend|reviewed .* levels|explain .* level|is this improving/i.test(prompt);
    const useStructuredPath = isSummaryPrompt || isCoachingPrompt;
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: prompt }, { role: 'assistant', content: '' }]);
    setIsStreaming(true);

    let accumulator = '';
    let streamMetadata: {
      num_sources?: number;
      sources?: ChatSource[];
      structured_data?: Record<string, unknown> | null;
    } = {};
    try {
      if (useStructuredPath) {
        const response = await api.chatAsk(patientId, prompt, {
          use_conversation_history: false,
          structured: true,
          coachingMode: isCoachingPrompt,
          clinicianMode: Boolean(clinicianMode),
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
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: response.answer,
            sources,
            num_sources: numSources,
            structured_data: structuredData,
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
          clinicianMode,
          onMetadata: (metadata) => {
            streamMetadata = {
              num_sources: metadata.num_sources,
              sources: metadata.sources,
              structured_data: metadata.structured_data ?? null,
            };
            setMessages((prev) => {
              const updated = [...prev];
              const currentContent = accumulator || updated[updated.length - 1]?.content || '';
              updated[updated.length - 1] = {
                role: 'assistant',
                content: currentContent,
                sources: streamMetadata.sources,
                num_sources: streamMetadata.num_sources,
                structured_data: streamMetadata.structured_data,
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
  }, [patientId, question, isStreaming, onError, clinicianMode]);

  const sendVision = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming) return;
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
  }, [patientId, isStreaming, onError]);

  const pushMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  const sendVolume = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming) return;
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
  }, [patientId, isStreaming, onError]);

  const sendWsi = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming) return;
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
  }, [patientId, isStreaming, onError]);

  const sendCxrCompare = useCallback(async (currentFile: File, priorFile: File, promptOverride?: string) => {
    if (isStreaming) return;
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
  }, [patientId, isStreaming, onError]);

  return {
    messages,
    question,
    setQuestion,
    isStreaming,
    send,
    sendVision,
    sendVolume,
    sendWsi,
    sendCxrCompare,
    pushMessage,
  };
};

export default useChat;
