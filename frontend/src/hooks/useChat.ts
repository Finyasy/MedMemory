import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import useAppStore from '../store/useAppStore';
import type { ChatMessage } from '../types';

type UseChatOptions = {
  patientId: number;
  onError: (label: string, error: unknown) => void;
};

const initialMessages: ChatMessage[] = [
  {
    role: 'assistant',
    content:
      'Ask me about trends, medications, or any part of the patient record to generate a grounded response.',
  },
];

const useChat = ({ patientId, onError }: UseChatOptions) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    setMessages(initialMessages);
    setQuestion('');
    setIsStreaming(false);
  }, [patientId]);

  const send = useCallback(async () => {
    if (!question.trim() || isStreaming) return;
    const prompt = question.trim();
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: prompt }, { role: 'assistant', content: '' }]);
    setIsStreaming(true);

    let accumulator = '';
    try {
      await api.streamChat(
        patientId,
        prompt,
        (chunk) => {
          accumulator += chunk;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: 'assistant', content: accumulator };
            return updated;
          });
        },
        () => {
          setIsStreaming(false);
        },
      );
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        useAppStore.getState().setAccessToken(null);
      }
      onError('Chat failed', error);
      setIsStreaming(false);
    }
  }, [patientId, question, isStreaming, onError]);

  const sendVision = useCallback(async (file: File, promptOverride?: string) => {
    if (isStreaming) return;
    const prompt = promptOverride?.trim() || 'Analyze this medical image and summarize findings.';
    setQuestion('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: `${prompt}\n[Image: ${file.name}]` },
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
      { role: 'user', content: `${prompt}\n[Current: ${currentFile.name}, Prior: ${priorFile.name}]` },
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
