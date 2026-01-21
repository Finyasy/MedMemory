type PipelinePanelProps = {
  payload: string;
  status: string;
  isLoading: boolean;
  isDisabled?: boolean;
  onPayloadChange: (value: string) => void;
  onIngest: () => void;
};

const PipelinePanel = ({
  payload,
  status,
  isLoading,
  isDisabled = false,
  onPayloadChange,
  onIngest,
}: PipelinePanelProps) => {
  return (
    <div className="panel pipeline">
      <div className="panel-header">
        <h2>Data intake</h2>
        <span className="signal-chip">Labs + meds</span>
      </div>
      <div className="pipeline-steps">
        {isLoading ? (
          <>
            <div className="skeleton-row" />
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </>
        ) : (
          <>
            <div>
              <span>Labs</span>
              <strong>Ready for upload</strong>
              <small>Add lab results to see trends</small>
            </div>
            <div>
              <span>Medications</span>
              <strong>Track adherence</strong>
              <small>Add active meds to monitor</small>
            </div>
            <div>
              <span>Visits</span>
              <strong>Summaries supported</strong>
              <small>Add visit notes to follow progress</small>
            </div>
          </>
        )}
      </div>
      <textarea
        className="json-area"
        value={payload}
        onChange={(event) => onPayloadChange(event.target.value)}
        disabled={isLoading || isDisabled}
      />
      <button
        className="secondary-button full"
        type="button"
        onClick={onIngest}
        disabled={isLoading || isDisabled}
      >
        {isLoading ? 'Importing...' : 'Import data'}
      </button>
      {status && <p className="status-text">{status}</p>}
    </div>
  );
};

export default PipelinePanel;
