import { useState } from 'react';
import type { InsightsLabItem } from '../../api/generated';
import type { AppleHealthStepsTrendResponse, AppleHealthSyncStatusResponse } from '../../types';
import {
  getPatientStrings,
  normalizePatientLanguage,
  translateMetricName,
  type SupportedPatientLanguage,
} from '../../utils/patientLanguage';

type TrendsPanelProps = {
  hasDocuments: boolean;
  insightsLoading: boolean;
  insightSummary: string;
  recentLabs: InsightsLabItem[];
  a1cPath: string;
  appleHealthLoading: boolean;
  appleHealthStepsTrend: AppleHealthStepsTrendResponse | null;
  appleHealthSyncStatus: AppleHealthSyncStatusResponse | null;
  appleHealthStepsPath: string;
  onRetryAppleHealthStatus: () => void | Promise<void>;
  onAskQuestion: () => void;
  formatDate: (date: string) => string;
  language?: SupportedPatientLanguage;
};

function TrendsPanel({
  hasDocuments,
  insightsLoading,
  insightSummary,
  recentLabs,
  a1cPath,
  appleHealthLoading,
  appleHealthStepsTrend,
  appleHealthSyncStatus,
  appleHealthStepsPath,
  onRetryAppleHealthStatus,
  onAskQuestion,
  formatDate,
  language = 'en',
}: TrendsPanelProps) {
  const resolvedLanguage = normalizePatientLanguage(language);
  const strings = getPatientStrings(resolvedLanguage);
  const hasLabs = recentLabs.length > 0;
  const [showSetupSteps, setShowSetupSteps] = useState(false);
  const [showAppleHealthSetup, setShowAppleHealthSetup] = useState(false);
  const appleHealthPoints = appleHealthStepsTrend?.points ?? [];
  const hasAppleHealthData = appleHealthPoints.length > 0;
  const appleHealthStatus = appleHealthSyncStatus?.status ?? 'disconnected';
  const appleHealthLastSyncedAt =
    appleHealthSyncStatus?.last_synced_at ?? appleHealthStepsTrend?.last_synced_at ?? null;
  const latestAppleHealthPoint = hasAppleHealthData ? appleHealthPoints[appleHealthPoints.length - 1] : null;
  const appleHealthAverage = appleHealthStepsTrend?.average_steps;
  const appleHealthTotal = appleHealthStepsTrend?.total_steps ?? 0;
  const shouldShowAppleHealthPanel =
    appleHealthLoading || hasAppleHealthData || Boolean(appleHealthSyncStatus);
  const appleHealthHasError = Boolean(appleHealthSyncStatus?.last_error) || appleHealthStatus === 'error';
  const appleHealthEmptyStateVisible =
    shouldShowAppleHealthPanel && !appleHealthLoading && !hasAppleHealthData;
  const combinedTrendEmptyState = !hasLabs && appleHealthEmptyStateVisible;

  const formatCompactDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });

  return (
    <div className={`insight-panel trends ${!hasLabs && !hasDocuments ? 'empty-guidance' : ''}`}>
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">{strings.trendsEyebrow}</p>
          <h2>{hasLabs ? strings.trendsTitle : strings.trendsSetupTitle}</h2>
          <p className="subtitle">{insightsLoading ? 'Loading trends...' : insightSummary}</p>
        </div>
        {hasLabs ? (
          <button className="ghost-button compact" type="button" onClick={onAskQuestion}>
            {strings.askQuestionLabel}
          </button>
        ) : null}
      </div>
      {shouldShowAppleHealthPanel ? (
        <div className="trend-subpanel" aria-label="Apple Health steps">
          <div className="trend-subpanel-header">
            <div>
              <p className="eyebrow">Apple Health (beta)</p>
              <h3>{strings.dailyStepsTitle}</h3>
            </div>
            <span className={`connection-status status-${appleHealthStatus}`}>
              {appleHealthStatus}
            </span>
          </div>
          {appleHealthLoading ? (
            <p className="dashboard-empty">Loading Apple Health steps…</p>
          ) : (
            <>
              <div className="trend-pill-row">
                <span className="trend-pill">
                  {appleHealthSyncStatus?.total_synced_days ?? appleHealthPoints.length} day
                  {(appleHealthSyncStatus?.total_synced_days ?? appleHealthPoints.length) === 1 ? '' : 's'} synced
                </span>
                <span className="trend-pill">
                  {appleHealthLastSyncedAt ? `Last sync ${formatDate(appleHealthLastSyncedAt)}` : 'Not synced yet'}
                </span>
              </div>
              {appleHealthSyncStatus?.last_error ? (
                <p className="connection-error">{appleHealthSyncStatus.last_error}</p>
              ) : null}
              {hasAppleHealthData ? (
                <>
                  {appleHealthStepsPath ? (
                    <svg
                      className="trend-chart steps-trend-chart"
                      viewBox="0 0 320 90"
                      role="img"
                      aria-label="Apple Health daily steps trend"
                    >
                      <path d={appleHealthStepsPath} />
                    </svg>
                  ) : null}
                  <div className="trend-list">
                    <div className="trend-item">
                      <div>
                        <h4>{strings.latestStepsLabel}</h4>
                        <span>
                          {latestAppleHealthPoint?.sample_date
                            ? formatCompactDate(latestAppleHealthPoint.sample_date)
                            : 'Most recent day'}
                        </span>
                      </div>
                      <div className="trend-metric flat">
                        <strong>{latestAppleHealthPoint?.step_count?.toLocaleString() ?? '—'}</strong>
                        <small>{strings.stepsUnit}</small>
                      </div>
                    </div>
                    <div className="trend-item">
                      <div>
                        <h4>{strings.averageStepsLabel}</h4>
                        <span>{appleHealthPoints.length} day window</span>
                      </div>
                      <div className="trend-metric up">
                        <strong>
                          {typeof appleHealthAverage === 'number'
                            ? Math.round(appleHealthAverage).toLocaleString()
                            : '—'}
                        </strong>
                        <small>{strings.stepsPerDayUnit}</small>
                      </div>
                    </div>
                    <div className="trend-item">
                      <div>
                        <h4>{strings.totalStepsLabel}</h4>
                        <span>
                          {appleHealthStepsTrend?.start_date && appleHealthStepsTrend?.end_date
                            ? `${formatCompactDate(appleHealthStepsTrend.start_date)} - ${formatCompactDate(appleHealthStepsTrend.end_date)}`
                            : 'Current window'}
                        </span>
                      </div>
                      <div className="trend-metric flat">
                        <strong>{appleHealthTotal.toLocaleString()}</strong>
                        <small>{strings.stepsUnit}</small>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <p className="dashboard-empty">
                    {appleHealthStatus === 'disconnected'
                      ? 'Set up iPhone sync to import daily steps into MedMemory.'
                      : 'No Apple Health steps synced yet. Run Sync now from the iPhone app to populate this trend.'}
                  </p>
                  <div className="trend-subpanel-actions">
                    <button
                      className="ghost-button compact"
                      type="button"
                      onClick={() => setShowAppleHealthSetup((prev) => !prev)}
                    >
                      {showAppleHealthSetup ? 'Hide iPhone setup' : 'Set up iPhone sync'}
                    </button>
                    {appleHealthHasError ? (
                      <button
                        className="ghost-button compact"
                        type="button"
                        disabled={appleHealthLoading}
                        onClick={() => {
                          void onRetryAppleHealthStatus();
                        }}
                      >
                        {appleHealthLoading ? 'Checking…' : 'Retry status check'}
                      </button>
                    ) : null}
                  </div>
                  {showAppleHealthSetup ? (
                    <div className="trend-setup-card">
                      <p className="dashboard-empty">
                        iPhone sync MVP scaffold is available in <code>ios/MedMemoryHealthSyncMVP</code>.
                      </p>
                      <ol className="trend-setup-list">
                        <li>Open the SwiftUI MVP in Xcode and enable the HealthKit capability.</li>
                        <li>Set your MedMemory API base URL, patient ID, and auth token.</li>
                        <li>Grant Apple Health step access and tap <strong>Sync now</strong>.</li>
                      </ol>
                    </div>
                  ) : null}
                </>
              )}
            </>
          )}
        </div>
      ) : null}
      {hasLabs ? (
        <>
          <svg className="trend-chart" viewBox="0 0 320 90" role="img" aria-label="A1C trend">
            <path d={a1cPath} />
          </svg>
          <div className="trend-list">
            {recentLabs.map((lab) => (
              <div key={lab.test_name} className="trend-item">
                <div>
                  <h4>{translateMetricName(lab.test_name, resolvedLanguage)}</h4>
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
              {combinedTrendEmptyState
                ? 'No trends yet. Upload a medical document for lab trends or connect iPhone sync for step trends.'
                : 'No trendable lab values yet. Add a document or ask a quick question to begin.'}
            </p>
            <div className="empty-guidance-actions">
              <button className="ghost-button compact" type="button" onClick={onAskQuestion}>
                Ask in chat
              </button>
              {combinedTrendEmptyState ? (
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => setShowAppleHealthSetup((prev) => !prev)}
                >
                  {showAppleHealthSetup ? 'Hide iPhone setup' : 'Set up iPhone sync'}
                </button>
              ) : null}
              <button
                className="ghost-button compact"
                type="button"
                onClick={() => setShowSetupSteps((prev) => !prev)}
              >
                {showSetupSteps ? 'Hide record setup' : 'Show record setup'}
              </button>
            </div>
          </div>
          {combinedTrendEmptyState && showAppleHealthSetup ? (
            <div className="trend-setup-card">
              <p className="dashboard-empty">
                iPhone sync MVP scaffold is available in <code>ios/MedMemoryHealthSyncMVP</code>.
              </p>
              <ol className="trend-setup-list">
                <li>Open the SwiftUI MVP in Xcode and enable the HealthKit capability.</li>
                <li>Set your MedMemory API base URL, patient ID, and auth token.</li>
                <li>Grant Apple Health step access and tap <strong>Sync now</strong>.</li>
              </ol>
            </div>
          ) : null}
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
