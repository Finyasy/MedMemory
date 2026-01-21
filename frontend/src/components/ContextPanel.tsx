type ContextPanelProps = {
  question: string;
  result: string;
  isLoading: boolean;
  isDisabled?: boolean;
  onQuestionChange: (value: string) => void;
  onGenerate: () => void;
};

const ContextPanel = ({
  question,
  result,
  isLoading,
  isDisabled = false,
  onQuestionChange,
  onGenerate,
}: ContextPanelProps) => {
  return (
    <div className="panel context">
      <div className="panel-header">
        <h2>Answer preview</h2>
        <span className="signal-chip">Preview</span>
      </div>
      <div className="search-row">
        <input
          type="text"
          placeholder="Question for context"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          aria-label="Context question"
          disabled={isLoading || isDisabled}
        />
        <button className="secondary-button" type="button" onClick={onGenerate} disabled={isLoading || isDisabled}>
          {isLoading ? 'Generating...' : 'Generate'}
        </button>
      </div>
      <div className="context-output">
        {isDisabled ? (
          <span className="empty-state">Select a patient to generate context.</span>
        ) : isLoading ? (
          <div className="skeleton-row" />
        ) : result ? (
          result
        ) : (
          <span className="empty-state">Ask a question to preview the context.</span>
        )}
      </div>
    </div>
  );
};

export default ContextPanel;
