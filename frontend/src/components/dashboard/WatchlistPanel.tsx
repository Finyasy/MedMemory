import type { WatchMetric } from '../../types';

type WatchlistPanelProps = {
  watchMetricsLoading: boolean;
  watchMetrics: WatchMetric[];
  activeWatchMetricId: number | null;
  onRemoveWatchMetric: (watchMetric: WatchMetric) => void;
};

function WatchlistPanel({
  watchMetricsLoading,
  watchMetrics,
  activeWatchMetricId,
  onRemoveWatchMetric,
}: WatchlistPanelProps) {
  return (
    <div className="insight-panel watchlist-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Tracked metrics</h2>
          <p className="subtitle">Create thresholds to trigger alerts when values drift.</p>
        </div>
      </div>
      {watchMetricsLoading ? (
        <p className="dashboard-empty">Loading watchlist…</p>
      ) : watchMetrics.length ? (
        <ul className="watchlist-items">
          {watchMetrics.map((watchMetric) => (
            <li key={watchMetric.id} className="watchlist-item">
              <div>
                <h4>{watchMetric.metric_name}</h4>
                <p>
                  {watchMetric.lower_bound != null || watchMetric.upper_bound != null
                    ? `Bounds: ${watchMetric.lower_bound ?? '—'} to ${watchMetric.upper_bound ?? '—'}`
                    : 'No explicit bounds (uses source abnormal flag)'}
                </p>
              </div>
              <button
                type="button"
                className="ghost-button compact"
                onClick={() => onRemoveWatchMetric(watchMetric)}
                disabled={activeWatchMetricId !== null}
              >
                {activeWatchMetricId === watchMetric.id ? 'Removing…' : 'Remove'}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-empty">
          No watch metrics yet. Select a highlight and click “Watch metric”.
        </p>
      )}
    </div>
  );
}

export default WatchlistPanel;
