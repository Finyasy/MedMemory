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

  return { messages, question, setQuestion, isStreaming, send };
};

export default useChat;
