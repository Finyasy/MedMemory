import { useCallback, useRef, useEffect, useState } from 'react';
import type { ChatMessage } from '../types';

type ChatInterfaceProps = {
  messages: ChatMessage[];
  question: string;
  isStreaming: boolean;
  isDisabled?: boolean;
  selectedPatient?: { id: number; full_name: string; age?: number | null; gender?: string | null };
  showHeader?: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
  onUploadFile?: (file: File) => void;
};

type MessageWithImages = ChatMessage & {
  images?: string[];
};

const ChatInterface = ({
  messages,
  question,
  isStreaming,
  isDisabled = false,
  selectedPatient,
  showHeader = true,
  onQuestionChange,
  onSend,
  onUploadFile,
}: ChatInterfaceProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [previewImages, setPreviewImages] = useState<Map<number, string[]>>(new Map());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files || []);
      if (files.length > 0 && onUploadFile) {
        files.forEach((file) => onUploadFile(file));
      }
      if (event.target) {
        event.target.value = '';
      }
    },
    [onUploadFile],
  );

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      if (e.dataTransfer.files && e.dataTransfer.files.length > 0 && onUploadFile) {
        Array.from(e.dataTransfer.files).forEach((file) => {
          if (file.type.startsWith('image/') || file.type === 'application/pdf') {
            onUploadFile(file);
          }
        });
      }
    },
    [onUploadFile],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (question.trim() && !isStreaming && !isDisabled) {
          onSend();
        }
      }
    },
    [question, isStreaming, isDisabled, onSend],
  );

  const handleSend = useCallback(() => {
    if (question.trim() && !isStreaming && !isDisabled) {
      onSend();
    }
  }, [question, isStreaming, isDisabled, onSend]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [question]);

  return (
    <div className="chat-interface">
      {/* Header */}
      {showHeader ? (
        <header className="chat-header">
          <div className="chat-header-content">
            <div className="chat-logo">
              <div className="chat-logo-dot" />
              <h1>MedMemory</h1>
            </div>
            {selectedPatient ? (
              <div className="chat-patient-info">
                <span className="patient-name">{selectedPatient.full_name}</span>
                {(selectedPatient.age || selectedPatient.gender) && (
                  <span className="patient-meta">
                    {selectedPatient.age && `Age ${selectedPatient.age}`}
                    {selectedPatient.age && selectedPatient.gender && ' · '}
                    {selectedPatient.gender}
                  </span>
                )}
              </div>
            ) : null}
          </div>
        </header>
      ) : null}

      {/* Messages Area */}
      <div
        className={`chat-messages-container ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="chat-empty-state">
              <div className="empty-state-images">
                <div
                  className="empty-state-image empty-state-image-1"
                  style={{ backgroundImage: "url('/pics/IMG_3318.JPG')" }}
                />
                <div
                  className="empty-state-image empty-state-image-2"
                  style={{ backgroundImage: "url('/pics/IMG_3326.JPG')" }}
                />
              </div>
              <h2>How can I help you today?</h2>
              <p>Ask questions about patient records, upload medical documents, or get insights from lab results.</p>
              <div className="empty-state-actions">
                <button
                  className="example-button"
                  onClick={() => onQuestionChange('Summarize recent lab results')}
                  type="button"
                >
                  Summarize recent lab results
                </button>
                <button
                  className="example-button"
                  onClick={() => onQuestionChange('What medications is the patient currently taking?')}
                  type="button"
                >
                  Current medications
                </button>
                <button
                  className="example-button"
                  onClick={() => onQuestionChange('Show me abnormal values from the past year')}
                  type="button"
                >
                  Abnormal values
                </button>
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <div key={`message-${index}`} className={`message message-${message.role}`}>
                <div className="message-avatar">
                  {message.role === 'user' ? (
                    <div className="avatar-user">U</div>
                  ) : (
                    <div className="avatar-assistant">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="message-content">
                  <div className="message-text">
                    {message.content || (isStreaming && message.role === 'assistant' && index === messages.length - 1 ? (
                      <span className="streaming-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </span>
                    ) : '')}
                  </div>
                </div>
              </div>
            ))
          )}
          {isStreaming && messages.length > 0 && messages[messages.length - 1].role !== 'assistant' && (
            <div className="message message-assistant">
              <div className="message-avatar">
                <div className="avatar-assistant">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                </div>
              </div>
              <div className="message-content">
                <div className="message-text">
                  <span className="streaming-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <div className="chat-input-actions">
            <button
              className="chat-action-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || isDisabled}
              type="button"
              title="Upload image or document"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </button>
          </div>
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={isDisabled ? 'Select a patient to start chatting...' : 'Message MedMemory...'}
            value={question}
            onChange={(e) => onQuestionChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming || isDisabled}
            rows={1}
          />
          <button
            className="chat-send-button"
            onClick={handleSend}
            disabled={!question.trim() || isStreaming || isDisabled}
            type="button"
            title="Send message"
          >
            {isStreaming ? (
              <svg className="spinner" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" opacity="0.25" />
                <path
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <div className="chat-input-footer">
          <p>MedMemory can make mistakes. Verify important medical information.</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf,.txt,.docx"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          multiple
        />
      </div>
    </div>
  );
};

export default ChatInterface;
