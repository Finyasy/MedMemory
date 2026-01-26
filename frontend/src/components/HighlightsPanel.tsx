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
  hasData?: boolean;
};

const exampleQuestions = [
  "What medications am I on?",
  "Show my A1C trend",
  "When was my last checkup?",
  "Compare my labs to last year",
];

const supportedDocs = [
  { icon: "📋", label: "Lab reports" },
  { icon: "💊", label: "Prescriptions" },
  { icon: "🏥", label: "Discharge summaries" },
  { icon: "📷", label: "Medical images" },
];

const HighlightsPanel = ({ items, chartPath, isLoading = false, hasData = false }: HighlightsPanelProps) => {
  const showEmptyState = !hasData && !isLoading;

  if (showEmptyState) {
    return (
      <div className="panel highlights empty-state">
        <div className="panel-header">
          <h2>Your Medical Memory</h2>
          <span className="signal-chip ai">AI-Powered</span>
        </div>
        <p className="panel-subtitle">
          Upload your health records and let AI help you understand them.
        </p>
        
        <div className="empty-feature-grid">
          <div className="empty-feature">
            <span className="feature-icon">🔍</span>
            <div>
              <h4>Ask anything</h4>
              <p>Natural language questions about your health</p>
            </div>
          </div>
          <div className="empty-feature">
            <span className="feature-icon">📈</span>
            <div>
              <h4>Track trends</h4>
              <p>See how your labs change over time</p>
            </div>
          </div>
          <div className="empty-feature">
            <span className="feature-icon">🧠</span>
            <div>
              <h4>AI analysis</h4>
              <p>MedGemma interprets scans and reports</p>
            </div>
          </div>
        </div>

        <div className="empty-docs-section">
          <p className="eyebrow">Supported documents</p>
          <div className="doc-types">
            {supportedDocs.map((doc) => (
              <span key={doc.label} className="doc-type-chip">
                {doc.icon} {doc.label}
              </span>
            ))}
          </div>
        </div>

        <div className="empty-questions-section">
          <p className="eyebrow">Try asking</p>
          <div className="example-questions">
            {exampleQuestions.map((q) => (
              <span key={q} className="example-question">"{q}"</span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel highlights">
      <div className="panel-header">
        <h2>Highlights</h2>
        <span className="signal-chip">Metabolic</span>
      </div>
      <p className="panel-subtitle">
        {items.length > 0 
          ? "Your recent lab results and health metrics at a glance."
          : "Upload lab reports to see your health metrics here."}
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
