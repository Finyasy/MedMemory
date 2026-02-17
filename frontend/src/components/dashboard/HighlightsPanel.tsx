import type { DashboardSummary, HighlightItem } from '../../types';

type HighlightsPanelProps = {
  loading: boolean;
  summary: DashboardSummary | null | undefined;
  items: HighlightItem[];
  selectedMetricKey: string | null;
  onSelectMetric: (metricKey: string) => void;
  formatDate: (date: string) => string;
  formatMetricReading: (
    value: string | null | undefined,
    numericValue: number | null | undefined,
    unit: string | null | undefined,
  ) => string;
  formatNumber: (value: number) => string;
};

function HighlightsPanel({
  loading,
  summary,
  items,
  selectedMetricKey,
  onSelectMetric,
  formatDate,
  formatMetricReading,
  formatNumber,
}: HighlightsPanelProps) {
  return (
    <div className="insight-panel highlights-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Highlights</p>
          <h2>Priority metrics</h2>
          <p className="subtitle">
            {summary
              ? `${summary.out_of_range} out of range · ${summary.in_range} in range`
              : 'Review your latest values and select one for details.'}
          </p>
        </div>
      </div>
      {loading ? (
        <p className="dashboard-empty">Loading highlights…</p>
      ) : items.length ? (
        <ul className="highlight-list">
          {items.map((item) => (
            <li key={`${item.metric_key}-${item.source_id ?? 'latest'}`}>
              <button
                type="button"
                className={`highlight-item ${selectedMetricKey === item.metric_key ? 'active' : ''}`}
                onClick={() => onSelectMetric(item.metric_key)}
              >
                <div className="highlight-item-main">
                  <h4>{item.metric_name}</h4>
                  <span className={`metric-status ${item.status}`}>
                    {item.status === 'out_of_range' ? 'Out of range' : 'In range'}
                  </span>
                </div>
                <div className="highlight-item-value">
                  <strong>{formatMetricReading(item.value, item.numeric_value, item.unit)}</strong>
                  <span>{item.observed_at ? formatDate(item.observed_at) : 'Latest result'}</span>
                </div>
                <p className="highlight-item-trend">
                  {typeof item.trend_delta === 'number'
                    ? `${item.trend_delta > 0 ? '↑' : item.trend_delta < 0 ? '↓' : '→'} ${formatNumber(Math.abs(item.trend_delta))}${item.unit ? ` ${item.unit}` : ''} vs prior`
                    : 'No prior value for trend comparison'}
                </p>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-empty">No highlight metrics yet. Upload a recent lab report to populate this panel.</p>
      )}
    </div>
  );
}

export default HighlightsPanel;
