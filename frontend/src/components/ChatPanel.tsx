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
  onUploadFile?: (file: File | File[]) => void;
  onLocalizeFile?: (file: File) => void;
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
  onLocalizeFile,
}: ChatPanelProps) => {
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0 && onUploadFile) {
      onUploadFile(Array.from(files));
    }
    event.target.value = '';
  };

  return (
    <div className="panel chat">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Patient Memory Chat</h2>
          <p>Ask questions, upload reports, images, CT/MRI volumes, WSI patch zips, or a CXR to compare.</p>
        </div>
        <span className="signal-chip">Live</span>
      </div>
      <div className="chat-window" aria-busy={isStreaming}>
        {isDisabled ? (
          <div className="empty-state">Select a patient to start chatting.</div>
        ) : messages.length === 0 ? (
          <div className="empty-state">
            Upload a report, image, volume (NIfTI / zipped DICOM), WSI patches (.zip), or a CXR to compare, or ask
            “Summarize recent labs” or “What changed in the last visit?”
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
          <label
            className="chat-upload tooltip"
            data-tooltip="Upload image(s), document, CT/MRI volume (.nii/.zip), WSI patches, or a CXR"
          >
            <input
              type="file"
              accept="image/*,.pdf,.txt,.docx,.zip,.nii,.nii.gz,.dcm"
              onChange={handleFileChange}
              disabled={isStreaming || isDisabled || isUploading}
              multiple
            />
            {isUploading ? 'Uploading…' : 'Add report'}
          </label>
          {onLocalizeFile ? (
            <label className="chat-upload tooltip" data-tooltip="Localize findings in an image">
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    onLocalizeFile(file);
                  }
                  event.target.value = '';
                }}
                disabled={isStreaming || isDisabled || isUploading}
              />
              Localize
            </label>
          ) : null}
          <button type="button" onClick={onSend} disabled={isStreaming || isDisabled}>
            {isStreaming ? 'Streaming' : 'Send'}
          </button>
        </div>
        <div className="chat-upload-hint">
          Supports NIfTI (.nii/.nii.gz), zipped DICOM, WSI patch zips, or a chest X-ray with history.
        </div>
        {uploadStatus && <div className="chat-upload-status">{uploadStatus}</div>}
      </div>
    </div>
  );
};

export default ChatPanel;
