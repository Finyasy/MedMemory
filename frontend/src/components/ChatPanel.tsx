import type { ChatMessage } from '../types';

type ChatPanelProps = {
  messages: ChatMessage[];
  question: string;
  isStreaming: boolean;
  isDisabled?: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
};

const ChatPanel = ({
  messages,
  question,
  isStreaming,
  isDisabled = false,
  onQuestionChange,
  onSend,
}: ChatPanelProps) => {
  return (
    <div className="panel chat">
      <div className="panel-header">
        <h2>Clinical Chat</h2>
        <span className="signal-chip">RAG Live</span>
      </div>
      <div className="chat-window" aria-busy={isStreaming}>
        {isDisabled ? (
          <div className="empty-state">Select a patient to start chatting.</div>
        ) : (
          messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
              {message.content || (isStreaming && message.role === 'assistant' ? '...' : '')}
            </div>
          ))
        )}
      </div>
      <div className="chat-input">
        <input
          type="text"
          placeholder="Ask a clinical question"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          aria-label="Chat question"
          disabled={isStreaming || isDisabled}
        />
        <button type="button" onClick={onSend} disabled={isStreaming || isDisabled}>
          {isStreaming ? 'Streaming' : 'Send'}
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;
