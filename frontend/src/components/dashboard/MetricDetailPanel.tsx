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
  const freshnessLabel = (days: number | null | undefined) => {
    if (typeof days !== 'number') return null;
    if (days <= 0) return 'Fresh today';
    if (days === 1) return '1 day old';
    return `${days} days old`;
  };

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
              {formatMetricReading(
                metricDetail.latest_normalized_value_text ?? metricDetail.latest_value,
                metricDetail.latest_normalized_value ?? metricDetail.latest_numeric_value,
                metricDetail.normalized_unit ?? metricDetail.unit,
              )}
            </p>
            <div className="metric-hero-meta">
              <span className={`metric-range-pill ${metricDetail.in_range === false ? 'out' : 'in'}`}>
                {metricDetail.in_range === false ? 'Out of range' : 'In range/unknown'}
              </span>
              <span>Reference: {metricDetail.reference_range || 'Not provided'}</span>
              {metricDetail.normalization_applied && metricDetail.normalized_unit ? (
                <span>Normalized to {metricDetail.normalized_unit}</span>
              ) : null}
              {metricDetail.latest_confidence_label ? (
                <span className={`metric-confidence-pill ${metricDetail.latest_confidence_label}`}>
                  {metricDetail.latest_confidence_label} confidence
                </span>
              ) : null}
              {freshnessLabel(metricDetail.latest_freshness_days) ? (
                <span>{freshnessLabel(metricDetail.latest_freshness_days)}</span>
              ) : null}
              {metricDetail.latest_source_id != null ? (
                <span>
                  Source: {(metricDetail.latest_source_type || 'record').replace(/_/g, ' ')} #{metricDetail.latest_source_id}
                </span>
              ) : null}
            </div>
          </div>
          <p className="metric-about">{metricDetail.about}</p>
          {metricDetail.excluded_points_count ? (
            <p className="metric-excluded-summary">
              {metricDetail.excluded_points_count} low-confidence point
              {metricDetail.excluded_points_count === 1 ? '' : 's'} excluded from automatic insights.
            </p>
          ) : null}
          {metricTrendPath ? (
            <svg className="trend-chart metric-trend-chart" viewBox="0 0 320 90" role="img" aria-label="Metric trend">
              <path d={metricTrendPath} />
            </svg>
          ) : null}
          <div className="metric-trend-list">
            {metricDetail.trend.slice().reverse().slice(0, 6).map((point, index) => (
              <div
                key={`${point.source_id ?? index}-${point.observed_at ?? 'latest'}`}
                className={`metric-trend-row ${point.excluded_from_insights ? 'excluded' : ''}`}
              >
                <div className="metric-trend-meta">
                  <span>{point.observed_at ? formatDate(point.observed_at) : 'Latest'}</span>
                  {point.source_id != null ? (
                    <span className="metric-trend-source">
                      {(point.source_type || 'record').replace(/_/g, ' ')} #{point.source_id}
                    </span>
                  ) : null}
                  {point.provider_name ? <span className="metric-trend-source">{point.provider_name}</span> : null}
                  {(point.confidence_label || typeof point.freshness_days === 'number') ? (
                    <span className="metric-trend-source">
                      {point.confidence_label ? `${point.confidence_label} confidence` : ''}
                      {point.confidence_label && typeof point.freshness_days === 'number' ? ' · ' : ''}
                      {freshnessLabel(point.freshness_days) || ''}
                    </span>
                  ) : null}
                </div>
                <div className="metric-trend-reading">
                  <strong>
                    {formatMetricReading(
                      point.normalized_value_text ?? point.value_text,
                      point.normalized_value ?? point.value,
                      point.normalized_unit ?? metricDetail.normalized_unit ?? metricDetail.unit,
                    )}
                  </strong>
                  {(point.raw_unit &&
                    point.normalized_unit &&
                    point.raw_unit !== point.normalized_unit) ? (
                    <span>
                      Raw {formatMetricReading(point.raw_value_text, point.raw_value, point.raw_unit)}
                    </span>
                  ) : null}
                  {point.excluded_from_insights ? (
                    <span className="metric-excluded-flag">Excluded from automatic insights</span>
                  ) : null}
                </div>
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
