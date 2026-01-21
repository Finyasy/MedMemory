import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
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

  return { messages, question, setQuestion, isStreaming, send, sendVision };
};

export default useChat;
