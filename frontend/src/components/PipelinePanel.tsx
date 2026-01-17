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
        <h2>Ingestion Pipeline</h2>
        <span className="signal-chip">Labs + Meds</span>
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
              <strong>112 panels</strong>
              <small>Batch ingestion ready</small>
            </div>
            <div>
              <span>Medications</span>
              <strong>38 active</strong>
              <small>Discontinue workflow</small>
            </div>
            <div>
              <span>Encounters</span>
              <strong>52 visits</strong>
              <small>SOAP notes supported</small>
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
        {isLoading ? 'Ingesting...' : 'Start Bulk Ingestion'}
      </button>
      {status && <p className="status-text">{status}</p>}
    </div>
  );
};

export default PipelinePanel;
