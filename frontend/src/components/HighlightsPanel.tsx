type HighlightItem = {
  title: string;
  value: string;
  trend: string;
  note: string;
};

type HighlightsPanelProps = {
  items: HighlightItem[];
  chartPath: string;
  isLoading?: boolean;
};

const HighlightsPanel = ({ items, chartPath, isLoading = false }: HighlightsPanelProps) => {
  return (
    <div className="panel highlights">
      <div className="panel-header">
        <h2>Highlights</h2>
        <span className="signal-chip">Metabolic</span>
      </div>
      <p className="panel-subtitle">
        Your LDL is improving, but still elevated. Vitamin D and PSA are trending low.
      </p>
      <div className="highlight-list">
        {isLoading ? (
          <>
            <div className="skeleton-row" />
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </>
        ) : (
          items.map((item) => (
            <div key={item.title} className="highlight-row">
              <div>
                <p className="highlight-title">{item.title}</p>
                <p className="highlight-note">{item.note}</p>
              </div>
              <div className="highlight-value">
                <span>{item.value}</span>
                <span className={`trend ${item.trend}`}>{item.trend}</span>
              </div>
            </div>
          ))
        )}
      </div>
      <div className="mini-chart">
        <h3>A1C Trend</h3>
        {isLoading ? (
          <div className="skeleton-card" aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 260 80" role="img" aria-label="A1C trend">
            <path d={chartPath} fill="none" stroke="var(--accent-strong)" strokeWidth="3" />
          </svg>
        )}
      </div>
    </div>
  );
};

export default HighlightsPanel;
