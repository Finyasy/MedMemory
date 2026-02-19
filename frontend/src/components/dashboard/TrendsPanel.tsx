import { useState } from 'react';
import type { InsightsLabItem } from '../../api/generated';

type TrendsPanelProps = {
  hasDocuments: boolean;
  insightsLoading: boolean;
  insightSummary: string;
  recentLabs: InsightsLabItem[];
  a1cPath: string;
  onAskQuestion: () => void;
  formatDate: (date: string) => string;
};

function TrendsPanel({
  hasDocuments,
  insightsLoading,
  insightSummary,
  recentLabs,
  a1cPath,
  onAskQuestion,
  formatDate,
}: TrendsPanelProps) {
  const hasLabs = recentLabs.length > 0;
  const [showSetupSteps, setShowSetupSteps] = useState(false);

  return (
    <div className={`insight-panel trends ${!hasLabs && !hasDocuments ? 'empty-guidance' : ''}`}>
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Trends</p>
          <h2>{hasLabs ? 'A1C over time' : 'Trends setup'}</h2>
          <p className="subtitle">{insightsLoading ? 'Loading trends...' : insightSummary}</p>
        </div>
        {hasLabs ? (
          <button className="ghost-button compact" type="button" onClick={onAskQuestion}>
            Ask a question
          </button>
        ) : null}
      </div>
      {hasLabs ? (
        <>
          <svg className="trend-chart" viewBox="0 0 320 90" role="img" aria-label="A1C trend">
            <path d={a1cPath} />
          </svg>
          <div className="trend-list">
            {recentLabs.map((lab) => (
              <div key={lab.test_name} className="trend-item">
                <div>
                  <h4>{lab.test_name}</h4>
                  <span>{lab.collected_at ? formatDate(lab.collected_at) : 'Latest'}</span>
                </div>
                <div className={`trend-metric ${lab.is_abnormal ? 'down' : 'flat'}`}>
                  <strong>
                    {lab.value || '—'} {lab.unit || ''}
                  </strong>
                  <small>{lab.is_abnormal ? 'abnormal' : 'stable'}</small>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-guidance-content">
          <div className="empty-guidance-compact">
            <p className="dashboard-empty">
              No trendable lab values yet. Add a document or ask a quick question to begin.
            </p>
            <div className="empty-guidance-actions">
              <button className="ghost-button compact" type="button" onClick={onAskQuestion}>
                Ask in chat
              </button>
              <button
                className="ghost-button compact"
                type="button"
                onClick={() => setShowSetupSteps((prev) => !prev)}
              >
                {showSetupSteps ? 'Hide setup steps' : 'Show setup steps'}
              </button>
            </div>
          </div>
          {showSetupSteps ? (
            <div className="empty-guidance-steps">
              <div className="guidance-step">
                <span className="step-number">1</span>
                <div>
                  <h4>Upload medical documents</h4>
                  <p>Lab reports, prescriptions, discharge summaries, or medical images</p>
                </div>
              </div>
              <div className="guidance-step">
                <span className="step-number">2</span>
                <div>
                  <h4>
                    AI extracts the data <span className="ai-badge">MedGemma</span>
                  </h4>
                  <p>Values, dates, medications, and diagnoses are automatically extracted</p>
                </div>
              </div>
              <div className="guidance-step">
                <span className="step-number">3</span>
                <div>
                  <h4>Ask questions in plain English</h4>
                  <p>"What's my A1C trend?" or "When was my last colonoscopy?"</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default TrendsPanel;
