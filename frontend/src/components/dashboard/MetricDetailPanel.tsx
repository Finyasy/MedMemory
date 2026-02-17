import type { MetricDetail, WatchMetric } from '../../types';

type MetricDetailPanelProps = {
  metricDetail: MetricDetail | null;
  metricDetailLoading: boolean;
  selectedMetricKey: string | null;
  selectedWatchMetric: WatchMetric | null;
  activeWatchMetricId: number | null;
  metricTrendPath: string;
  onToggleWatchMetric: () => void;
  onAskInChat: () => void;
  formatDate: (date: string) => string;
  formatMetricReading: (
    value: string | null | undefined,
    numericValue: number | null | undefined,
    unit: string | null | undefined,
  ) => string;
};

function MetricDetailPanel({
  metricDetail,
  metricDetailLoading,
  selectedMetricKey,
  selectedWatchMetric,
  activeWatchMetricId,
  metricTrendPath,
  onToggleWatchMetric,
  onAskInChat,
  formatDate,
  formatMetricReading,
}: MetricDetailPanelProps) {
  return (
    <div className="insight-panel metric-detail-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Metric detail</p>
          <h2>{metricDetail?.metric_name ?? 'Select a highlight metric'}</h2>
          <p className="subtitle">
            {metricDetail?.observed_at
              ? `Observed ${formatDate(metricDetail.observed_at)}`
              : 'Pick a metric in Highlights to inspect trend and range.'}
          </p>
        </div>
        <div className="metric-detail-actions">
          <button
            className="ghost-button compact"
            type="button"
            onClick={onToggleWatchMetric}
            disabled={!selectedMetricKey || activeWatchMetricId !== null}
          >
            {activeWatchMetricId !== null
              ? 'Saving…'
              : selectedWatchMetric
                ? 'Unwatch metric'
                : 'Watch metric'}
          </button>
          <button
            className="ghost-button compact"
            type="button"
            onClick={onAskInChat}
            disabled={!metricDetail}
          >
            Ask in chat
          </button>
        </div>
      </div>
      {metricDetailLoading ? (
        <p className="dashboard-empty">Loading metric details…</p>
      ) : metricDetail ? (
        <>
          <div className="metric-hero">
            <p className="metric-hero-value">
              {formatMetricReading(metricDetail.latest_value, metricDetail.latest_numeric_value, metricDetail.unit)}
            </p>
            <div className="metric-hero-meta">
              <span className={`metric-range-pill ${metricDetail.in_range === false ? 'out' : 'in'}`}>
                {metricDetail.in_range === false ? 'Out of range' : 'In range/unknown'}
              </span>
              <span>Reference: {metricDetail.reference_range || 'Not provided'}</span>
            </div>
          </div>
          <p className="metric-about">{metricDetail.about}</p>
          {metricTrendPath ? (
            <svg className="trend-chart metric-trend-chart" viewBox="0 0 320 90" role="img" aria-label="Metric trend">
              <path d={metricTrendPath} />
            </svg>
          ) : null}
          <div className="metric-trend-list">
            {metricDetail.trend.slice().reverse().slice(0, 6).map((point, index) => (
              <div key={`${point.source_id ?? index}-${point.observed_at ?? 'latest'}`} className="metric-trend-row">
                <span>{point.observed_at ? formatDate(point.observed_at) : 'Latest'}</span>
                <strong>{formatMetricReading(point.value_text, point.value, metricDetail.unit)}</strong>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="dashboard-empty">
          No metric selected. Choose one from Highlights to see context, ranges, and trend history.
        </p>
      )}
    </div>
  );
}

export default MetricDetailPanel;
