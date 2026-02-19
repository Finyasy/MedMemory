import React, { useCallback, useRef, useEffect, useState } from 'react';
import type { ChatMessage, ChatSource } from '../types';

const FormattedMessage: React.FC<{ content: string }> = ({ content }) => {
  const formatContent = (text: string) => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      const headingMatch = trimmedLine.match(/^\*\*([^*]+?):?\*\*/);
      
      if (headingMatch) {
        const headingText = headingMatch[1].trim();
        const restOfLine = trimmedLine.substring(headingMatch[0].length).trim();
        
        elements.push(
          <React.Fragment key={index}>
            <span className="message-heading">{headingText}</span>
            {restOfLine && <span>{restOfLine}</span>}
            {index < lines.length - 1 && <br />}
          </React.Fragment>
        );
      } else if (trimmedLine.startsWith('* ') && !trimmedLine.match(/^\*\*\*/)) {
        // List item (starts with "* " but not "***")
        const listContent = trimmedLine.substring(2);
        // Process bold text within list items
        const formattedListContent = listContent.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            const boldText = part.slice(2, -2);
            return <strong key={partIndex}>{boldText}</strong>;
          }
          return <span key={partIndex}>{part}</span>;
        });
        
        elements.push(
          <React.Fragment key={index}>
            <span style={{ display: 'block', marginLeft: '1rem', marginTop: '0.5rem' }}>
              • {formattedListContent}
            </span>
            {index < lines.length - 1 && <br />}
          </React.Fragment>
        );
      } else if (trimmedLine) {
        const formattedLine = trimmedLine.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            const boldText = part.slice(2, -2);
            if (boldText.match(/^(Overview|Key results|What this means|Next steps|Overall|Blood|Urine|Important|What's|Next|Key|Summary|Results|Findings|Recommendations|Takeaways)/i)) {
              return <span key={partIndex} className="message-heading">{boldText}</span>;
            }
            return <strong key={partIndex}>{boldText}</strong>;
          }
          return <span key={partIndex}>{part}</span>;
        });
        
        elements.push(
          <React.Fragment key={index}>
            {formattedLine}
            {index < lines.length - 1 && <br />}
          </React.Fragment>
        );
      } else {
        elements.push(<br key={index} />);
      }
    });
    
    return elements;
  };
  
  return <>{formatContent(content)}</>;
};

const formatSourceLabel = (source: ChatSource) => {
  const base = source.source_type?.replace(/_/g, ' ') || 'source';
  if (source.source_id === null || source.source_id === undefined) {
    return base;
  }
  return `${base} #${source.source_id}`;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const toText = (value: unknown): string | null => {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
};

const toStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => toText(item))
    .filter((item): item is string => Boolean(item));
};

const toSectionSources = (value: unknown): Record<string, string[]> => {
  if (!isRecord(value)) return {};
  const sectionSources: Record<string, string[]> = {};
  Object.entries(value).forEach(([section, chips]) => {
    const parsed = toStringList(chips).slice(0, 6);
    if (parsed.length) sectionSources[section] = parsed;
  });
  return sectionSources;
};

const formatStructuredValue = (entry: Record<string, unknown>): string | null => {
  const name = toText(entry.name);
  const value = toText(entry.value);
  const unit = toText(entry.unit);
  const dosage = toText(entry.dosage);
  const frequency = toText(entry.frequency);
  const status = toText(entry.status);

  if (name && value) {
    return unit ? `${name}: ${value} ${unit}` : `${name}: ${value}`;
  }
  if (name && dosage && frequency) return `${name}: ${dosage} (${frequency})`;
  if (name && dosage) return `${name}: ${dosage}`;
  if (name && status) return `${name}: ${status}`;
  if (name) return name;
  return null;
};

type MessageBadge = {
  label: string;
  tone: 'good' | 'warn' | 'info';
};

const buildGuardrailBadges = (message: ChatMessage): MessageBadge[] => {
  if (message.role !== 'assistant') return [];
  const badges: MessageBadge[] = [];
  const content = message.content || '';
  const contentLower = content.toLowerCase();

  if (message.sources && message.sources.length > 0) {
    badges.push({ label: 'Grounded', tone: 'good' });
  }
  if (isRecord(message.structured_data)) {
    badges.push({ label: 'Structured', tone: 'info' });
  }
  if (content.includes('(source:')) {
    badges.push({ label: 'Cited', tone: 'good' });
  }
  if (
    content.includes('I do not know from the available records') ||
    content.includes('The document does not record') ||
    content.includes('does not explain this topic') ||
    contentLower.includes('no completed document text is available')
  ) {
    badges.push({ label: 'No Evidence', tone: 'warn' });
  }
  if (
    content.includes('not enough dated values') ||
    content.includes('please specify which test trend')
  ) {
    badges.push({ label: 'Insufficient Data', tone: 'warn' });
  }
  if (content.startsWith('From your records')) {
    badges.push({ label: 'Record-Based', tone: 'info' });
  }

  return badges;
};

const StructuredDataView: React.FC<{ structuredData: Record<string, unknown> }> = ({
  structuredData,
}) => {
  const overview = toText(structuredData.overview);
  const keyResults = Array.isArray(structuredData.key_results)
    ? structuredData.key_results
      .filter((item): item is Record<string, unknown> => isRecord(item))
      .map((item) => formatStructuredValue(item))
      .filter((item): item is string => Boolean(item))
    : [];
  const medications = Array.isArray(structuredData.medications)
    ? structuredData.medications
      .filter((item): item is Record<string, unknown> => isRecord(item))
      .map((item) => formatStructuredValue(item))
      .filter((item): item is string => Boolean(item))
    : [];
  const vitalSigns = isRecord(structuredData.vital_signs)
    ? Object.entries(structuredData.vital_signs)
      .map(([name, value]) => {
        const text = toText(value);
        return text ? `${name.replace(/_/g, ' ')}: ${text}` : null;
      })
      .filter((item): item is string => Boolean(item))
    : [];
  const followUps = toStringList(structuredData.follow_ups);
  const concerns = toStringList(structuredData.concerns);
  const whatChanged = toStringList(structuredData.what_changed);
  const whyItMatters = toStringList(structuredData.why_it_matters);
  const suggestedNext = toStringList(structuredData.suggested_next_discussion_points);
  const sectionSources = toSectionSources(structuredData.section_sources);

  const renderSectionSources = (sectionKey: string) => {
    const chips = sectionSources[sectionKey];
    if (!chips || chips.length === 0) return null;
    return (
      <div className="message-source-list message-structured-source-list">
        {chips.map((chip, idx) => (
          <span className="message-source-chip" key={`${sectionKey}-source-${idx}-${chip}`}>
            {chip}
          </span>
        ))}
      </div>
    );
  };

  if (!overview && keyResults.length === 0 && medications.length === 0
    && vitalSigns.length === 0 && followUps.length === 0 && concerns.length === 0
    && whatChanged.length === 0 && whyItMatters.length === 0 && suggestedNext.length === 0) {
    return null;
  }

  return (
    <div className="message-structured">
      {overview ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Overview</span>
          <span className="message-structured-text">{overview}</span>
          {renderSectionSources('overview')}
        </div>
      ) : null}

      {keyResults.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Key Results</span>
          <ul className="message-structured-list">
            {keyResults.slice(0, 6).map((item, idx) => (
              <li key={`key-result-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('key_results')}
        </div>
      ) : null}

      {medications.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Medications</span>
          <ul className="message-structured-list">
            {medications.slice(0, 6).map((item, idx) => (
              <li key={`medication-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('medications')}
        </div>
      ) : null}

      {vitalSigns.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Vital Signs</span>
          <ul className="message-structured-list">
            {vitalSigns.slice(0, 6).map((item, idx) => (
              <li key={`vitals-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('vital_signs')}
        </div>
      ) : null}

      {followUps.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Follow-ups</span>
          <ul className="message-structured-list">
            {followUps.slice(0, 6).map((item, idx) => (
              <li key={`follow-up-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('follow_ups')}
        </div>
      ) : null}

      {concerns.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Concerns</span>
          <ul className="message-structured-list">
            {concerns.slice(0, 6).map((item, idx) => (
              <li key={`concern-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('concerns')}
        </div>
      ) : null}

      {whatChanged.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">What Changed</span>
          <ul className="message-structured-list">
            {whatChanged.slice(0, 6).map((item, idx) => (
              <li key={`what-changed-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('what_changed')}
        </div>
      ) : null}

      {whyItMatters.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Why It Matters</span>
          <ul className="message-structured-list">
            {whyItMatters.slice(0, 6).map((item, idx) => (
              <li key={`why-it-matters-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('why_it_matters')}
        </div>
      ) : null}

      {suggestedNext.length > 0 ? (
        <div className="message-structured-section">
          <span className="message-structured-heading">Suggested Next Discussion Points</span>
          <ul className="message-structured-list">
            {suggestedNext.slice(0, 6).map((item, idx) => (
              <li key={`suggested-next-${idx}`}>{item}</li>
            ))}
          </ul>
          {renderSectionSources('suggested_next_discussion_points')}
        </div>
      ) : null}
    </div>
  );
};

type ChatInterfaceProps = {
  messages: ChatMessage[];
  question: string;
  isStreaming: boolean;
  isDisabled?: boolean;
  selectedPatient?: { id: number; full_name: string; age?: number | null; gender?: string | null; is_dependent?: boolean };
  showHeader?: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
  onUploadFile?: (file: File | File[]) => void;
  onLocalizeFile?: (file: File) => void;
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
  onLocalizeFile,
}: ChatInterfaceProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const localizeInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

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
        onUploadFile(files);
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
        onUploadFile(Array.from(e.dataTransfer.files));
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
              {selectedPatient?.is_dependent ? (
                <div className="dependent-empty-icon">👶</div>
              ) : (
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
              )}
              {selectedPatient?.is_dependent ? (
                <>
                  <h2>How can I help with {selectedPatient.full_name}'s health?</h2>
                  <p>Upload medical documents or ask questions about their health records.</p>
                </>
              ) : (
                <>
                  <h2>How can I help you today?</h2>
                  <p>Ask questions about patient records, upload medical documents, or get insights from lab results.</p>
                </>
              )}
              <div className="empty-state-actions">
                <button
                  className="example-button"
                  onClick={() => onQuestionChange(
                    selectedPatient?.is_dependent 
                      ? `Summarize ${selectedPatient.full_name}'s recent lab results`
                      : 'Summarize recent lab results'
                  )}
                  type="button"
                >
                  {selectedPatient?.is_dependent ? 'Recent lab results' : 'Summarize recent lab results'}
                </button>
                <button
                  className="example-button"
                  onClick={() => onQuestionChange(
                    selectedPatient?.is_dependent
                      ? `What medications is ${selectedPatient.full_name} currently taking?`
                      : 'What medications is the patient currently taking?'
                  )}
                  type="button"
                >
                  Current medications
                </button>
                <button
                  className="example-button"
                  onClick={() => onQuestionChange(
                    selectedPatient?.is_dependent
                      ? `Show ${selectedPatient.full_name}'s vaccination history`
                      : 'Show me abnormal values from the past year'
                  )}
                  type="button"
                >
                  {selectedPatient?.is_dependent ? 'Vaccination history' : 'Abnormal values'}
                </button>
              </div>
            </div>
          ) : (
            messages.map((message, index) => {
              const guardrailBadges = buildGuardrailBadges(message);
              return (
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
                      {message.role === 'assistant' && message.content ? (
                        <FormattedMessage content={message.content} />
                      ) : message.content || (isStreaming && message.role === 'assistant' && index === messages.length - 1 ? (
                        <span className="streaming-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </span>
                      ) : '')}
                    </div>
                    {message.role === 'assistant' && guardrailBadges.length > 0 ? (
                      <div className="message-badges">
                        {guardrailBadges.map((badge) => (
                          <span
                            key={`${badge.label}-${badge.tone}`}
                            className={`message-badge message-badge-${badge.tone}`}
                          >
                            {badge.label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {message.role === 'assistant' && message.sources && message.sources.length > 0 ? (
                      <div className="message-sources">
                        <span className="message-sources-label">
                          Sources {typeof message.num_sources === 'number' ? `(${message.num_sources})` : ''}
                        </span>
                        <div className="message-source-list">
                          {message.sources.slice(0, 5).map((source, sourceIndex) => (
                            <span className="message-source-chip" key={`${formatSourceLabel(source)}-${sourceIndex}`}>
                              {formatSourceLabel(source)}
                              {Number.isFinite(source.relevance)
                                ? ` ${Math.round(source.relevance * 100)}%`
                                : ''}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {message.role === 'assistant' && isRecord(message.structured_data) ? (
                      <StructuredDataView structuredData={message.structured_data} />
                    ) : null}
                  </div>
                </div>
              );
            })
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
              className="chat-action-button tooltip"
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || isDisabled}
              type="button"
              data-tooltip="Upload image(s), document, CT/MRI volume (.nii/.zip), WSI patches, or a CXR"
              aria-label="Upload image, document, CT/MRI volume, WSI patches, or a CXR"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </button>
            {onLocalizeFile ? (
              <button
                className="chat-action-button tooltip"
                onClick={() => localizeInputRef.current?.click()}
                disabled={isStreaming || isDisabled}
                type="button"
                data-tooltip="Localize findings in an image"
                aria-label="Localize findings in an image"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="7" />
                  <line x1="12" y1="2" x2="12" y2="6" />
                  <line x1="12" y1="18" x2="12" y2="22" />
                  <line x1="2" y1="12" x2="6" y2="12" />
                  <line x1="18" y1="12" x2="22" y2="12" />
                </svg>
              </button>
            ) : null}
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
            data-testid="chat-input"
          />
          <button
            className="chat-send-button"
            onClick={handleSend}
            disabled={!question.trim() || isStreaming || isDisabled}
            type="button"
            title="Send message"
            data-testid="chat-send"
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
          accept="image/*,.pdf,.txt,.docx,.zip,.nii,.nii.gz,.dcm"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          multiple
        />
        <input
          ref={localizeInputRef}
          type="file"
          accept="image/*"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file && onLocalizeFile) {
              onLocalizeFile(file);
            }
            event.target.value = '';
          }}
          style={{ display: 'none' }}
        />
      </div>
    </div>
  );
};

export default ChatInterface;
