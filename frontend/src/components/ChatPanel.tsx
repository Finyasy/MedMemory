import type { ChatMessage } from '../types';

type ChatPanelProps = {
  messages: ChatMessage[];
  question: string;
  isStreaming: boolean;
  isDisabled?: boolean;
  uploadStatus?: string;
  isUploading?: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
  onUploadFile?: (file: File) => void;
};

const ChatPanel = ({
  messages,
  question,
  isStreaming,
  isDisabled = false,
  uploadStatus,
  isUploading = false,
  onQuestionChange,
  onSend,
  onUploadFile,
}: ChatPanelProps) => {
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && onUploadFile) {
      onUploadFile(file);
    }
    event.target.value = '';
  };

  return (
    <div className="panel chat">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Patient Memory Chat</h2>
          <p>Ask questions, upload reports, and get grounded answers.</p>
        </div>
        <span className="signal-chip">Live</span>
      </div>
      <div className="chat-window" aria-busy={isStreaming}>
        {isDisabled ? (
          <div className="empty-state">Select a patient to start chatting.</div>
        ) : messages.length === 0 ? (
          <div className="empty-state">
            Upload a report or ask a question like “Summarize recent labs” or
            “What changed in the last visit?”
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
              {message.content || (isStreaming && message.role === 'assistant' ? '...' : '')}
            </div>
          ))
        )}
      </div>
      <div className="chat-composer">
        <textarea
          rows={2}
          placeholder="Ask about labs, medications, or a specific document..."
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          aria-label="Chat question"
          disabled={isStreaming || isDisabled}
        />
        <div className="chat-actions">
          <label className="chat-upload">
            <input
              type="file"
              accept="image/*,.pdf,.txt,.docx"
              onChange={handleFileChange}
              disabled={isStreaming || isDisabled || isUploading}
            />
            {isUploading ? 'Uploading…' : 'Add report'}
          </label>
          <button type="button" onClick={onSend} disabled={isStreaming || isDisabled}>
            {isStreaming ? 'Streaming' : 'Send'}
          </button>
        </div>
        {uploadStatus && <div className="chat-upload-status">{uploadStatus}</div>}
      </div>
    </div>
  );
};

export default ChatPanel;
