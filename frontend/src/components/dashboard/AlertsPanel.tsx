import type { MetricAlert } from '../../types';

type AlertsPanelProps = {
  metricAlertsLoading: boolean;
  metricAlerts: MetricAlert[];
  activeAlertsCount: number;
  alertsEvaluating: boolean;
  activeAlertId: number | null;
  onEvaluateAlerts: () => void;
  onAcknowledgeAlert: (alertId: number) => void;
  formatDate: (date: string) => string;
  formatMetricReading: (
    value: string | null | undefined,
    numericValue: number | null | undefined,
    unit: string | null | undefined,
  ) => string;
};

function AlertsPanel({
  metricAlertsLoading,
  metricAlerts,
  activeAlertsCount,
  alertsEvaluating,
  activeAlertId,
  onEvaluateAlerts,
  onAcknowledgeAlert,
  formatDate,
  formatMetricReading,
}: AlertsPanelProps) {
  return (
    <div className="insight-panel alerts-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Alerts</p>
          <h2>{activeAlertsCount} active</h2>
          <p className="subtitle">Evaluate watch rules against latest results.</p>
        </div>
        <button
          type="button"
          className="ghost-button compact"
          onClick={onEvaluateAlerts}
          disabled={alertsEvaluating}
        >
          {alertsEvaluating ? 'Checking…' : 'Evaluate now'}
        </button>
      </div>
      {metricAlertsLoading ? (
        <p className="dashboard-empty">Loading alerts…</p>
      ) : metricAlerts.length ? (
        <ul className="alert-list">
          {metricAlerts.map((alert) => (
            <li key={alert.id} className={`alert-item severity-${alert.severity}`}>
              <div className="alert-main">
                <h4>{alert.metric_name}</h4>
                <p>{alert.reason}</p>
                <span>
                  {formatMetricReading(alert.value_text, alert.numeric_value, alert.unit)}
                  {alert.observed_at ? ` · ${formatDate(alert.observed_at)}` : ''}
                </span>
                {alert.previous_value_text || alert.previous_numeric_value != null ? (
                  <span className="alert-change">
                    Prior {formatMetricReading(alert.previous_value_text, alert.previous_numeric_value, alert.unit)}
                    {alert.previous_observed_at ? ` · ${formatDate(alert.previous_observed_at)}` : ''}
                    {' '}→ Current {formatMetricReading(alert.value_text, alert.numeric_value, alert.unit)}
                    {typeof alert.trend_delta === 'number'
                      ? ` (Δ ${alert.trend_delta > 0 ? '+' : ''}${alert.trend_delta.toFixed(2).replace(/\.?0+$/, '')}${alert.unit ? ` ${alert.unit}` : ''})`
                      : ''}
                  </span>
                ) : null}
                <span className="alert-source">
                  {alert.source_type.replace(/_/g, ' ')}
                  {alert.source_id != null ? ` #${alert.source_id}` : ''}
                </span>
              </div>
              <button
                type="button"
                className="ghost-button compact"
                onClick={() => onAcknowledgeAlert(alert.id)}
                disabled={activeAlertId !== null}
              >
                {activeAlertId === alert.id ? 'Saving…' : 'Acknowledge'}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-empty">
          No active alerts. Run Evaluate to check watchlist metrics against latest data.
        </p>
      )}
    </div>
  );
}

export default AlertsPanel;
