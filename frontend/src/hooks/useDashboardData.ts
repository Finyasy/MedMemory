import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, api } from '../api';
import type {
  ClinicianAccessRequest,
  DataConnection,
  DashboardSummary,
  HighlightItem,
  MetricAlert,
  MetricDetail,
  WatchMetric,
} from '../types';
import type { InsightsLabItem, InsightsMedicationItem } from '../api/generated';

type LatestDocumentStatus = {
  chunks: { total: number; indexed: number; not_indexed: number };
  processing_status: string;
  processing_error: string | null;
};

type UseDashboardDataOptions = {
  patientId: number;
  isAuthenticated: boolean;
  hasSelectedPatient: boolean;
  hasCurrentUser: boolean;
  latestDocumentId?: number;
  setPatientId: (id: number | null) => void;
  handleError: (label: string, error: unknown) => void;
  pushToast: (type: 'success' | 'error' | 'info', message: string) => void;
};

type UseDashboardDataResult = {
  insights: {
    lab_total: number;
    lab_abnormal: number;
    recent_labs: InsightsLabItem[];
    active_medications: number;
    recent_medications: InsightsMedicationItem[];
    a1c_series: number[];
  } | null;
  insightsLoading: boolean;
  dashboardHighlightItems: HighlightItem[];
  dashboardSummary: DashboardSummary | null;
  dashboardHighlightsLoading: boolean;
  selectedMetricKey: string | null;
  setSelectedMetricKey: (metricKey: string | null) => void;
  metricDetail: MetricDetail | null;
  metricDetailLoading: boolean;
  watchMetrics: WatchMetric[];
  watchMetricsLoading: boolean;
  selectedWatchMetric: WatchMetric | null;
  metricAlerts: MetricAlert[];
  metricAlertsLoading: boolean;
  activeAlertsCount: number;
  alertsEvaluating: boolean;
  activeWatchMetricId: number | null;
  activeAlertId: number | null;
  dashboardConnectionLoading: boolean;
  dataConnections: DataConnection[];
  activeConnectionSlug: string | null;
  activeSyncConnectionId: number | null;
  ocrAvailable: boolean | null;
  latestDocumentStatus: LatestDocumentStatus | null;
  accessRequests: ClinicianAccessRequest[];
  accessRequestsLoading: boolean;
  actingGrantId: number | null;
  handleConnectProvider: (providerName: string, providerSlug: string) => Promise<void>;
  handleConnectionState: (connection: DataConnection) => Promise<void>;
  handleSyncConnection: (connection: DataConnection) => Promise<void>;
  handleToggleSelectedWatchMetric: () => Promise<void>;
  handleRemoveWatchMetric: (watchMetric: WatchMetric) => Promise<void>;
  handleEvaluateAlerts: () => Promise<void>;
  handleAcknowledgeAlert: (alertId: number) => Promise<void>;
  handleApproveAccess: (grantId: number) => Promise<void>;
  handleDenyAccess: (grantId: number) => Promise<void>;
};

const useDashboardData = ({
  patientId,
  isAuthenticated,
  hasSelectedPatient,
  hasCurrentUser,
  latestDocumentId,
  setPatientId,
  handleError,
  pushToast,
}: UseDashboardDataOptions): UseDashboardDataResult => {
  const [insights, setInsights] = useState<UseDashboardDataResult['insights']>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [dashboardHighlights, setDashboardHighlights] = useState<{
    patient_id: number;
    summary: DashboardSummary;
    highlights: HighlightItem[];
  } | null>(null);
  const [dashboardHighlightsLoading, setDashboardHighlightsLoading] = useState(false);
  const [selectedMetricKey, setSelectedMetricKey] = useState<string | null>(null);
  const [metricDetail, setMetricDetail] = useState<MetricDetail | null>(null);
  const [metricDetailLoading, setMetricDetailLoading] = useState(false);
  const [watchMetrics, setWatchMetrics] = useState<WatchMetric[]>([]);
  const [watchMetricsLoading, setWatchMetricsLoading] = useState(false);
  const [metricAlerts, setMetricAlerts] = useState<MetricAlert[]>([]);
  const [metricAlertsLoading, setMetricAlertsLoading] = useState(false);
  const [alertsEvaluating, setAlertsEvaluating] = useState(false);
  const [dashboardConnectionLoading, setDashboardConnectionLoading] = useState(false);
  const [dataConnections, setDataConnections] = useState<DataConnection[]>([]);
  const [activeConnectionSlug, setActiveConnectionSlug] = useState<string | null>(null);
  const [activeSyncConnectionId, setActiveSyncConnectionId] = useState<number | null>(null);
  const [activeWatchMetricId, setActiveWatchMetricId] = useState<number | null>(null);
  const [activeAlertId, setActiveAlertId] = useState<number | null>(null);
  const [ocrAvailable, setOcrAvailable] = useState<boolean | null>(null);
  const [latestDocumentStatus, setLatestDocumentStatus] = useState<LatestDocumentStatus | null>(null);
  const [accessRequests, setAccessRequests] = useState<ClinicianAccessRequest[]>([]);
  const [accessRequestsLoading, setAccessRequestsLoading] = useState(false);
  const [actingGrantId, setActingGrantId] = useState<number | null>(null);

  useEffect(() => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setInsights(null);
      return;
    }

    if (!hasSelectedPatient && hasCurrentUser) {
      setInsights(null);
      return;
    }

    setInsightsLoading(true);
    api.getPatientInsights(patientId)
      .then((data) => setInsights(data))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 404) {
          console.warn('Patient not found, clearing patientId');
          setPatientId(0);
          setInsights(null);
        } else {
          handleError('Failed to load insights', error);
        }
      })
      .finally(() => setInsightsLoading(false));
  }, [patientId, isAuthenticated, hasSelectedPatient, hasCurrentUser, setPatientId, handleError]);

  const loadDashboardConnections = useCallback(async () => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setDataConnections([]);
      return;
    }
    setDashboardConnectionLoading(true);
    try {
      const rows = await api.listDataConnections(patientId);
      setDataConnections(rows);
    } catch (error) {
      setDataConnections([]);
      handleError('Failed to load data connections', error);
    } finally {
      setDashboardConnectionLoading(false);
    }
  }, [patientId, isAuthenticated, handleError]);

  const loadDashboardHighlights = useCallback(async () => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setDashboardHighlights(null);
      return;
    }
    setDashboardHighlightsLoading(true);
    try {
      const response = await api.getDashboardHighlights(patientId, 6);
      setDashboardHighlights(response);
    } catch (error) {
      setDashboardHighlights(null);
      handleError('Failed to load health highlights', error);
    } finally {
      setDashboardHighlightsLoading(false);
    }
  }, [patientId, isAuthenticated, handleError]);

  const loadWatchMetrics = useCallback(async () => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setWatchMetrics([]);
      return;
    }
    setWatchMetricsLoading(true);
    try {
      const rows = await api.listWatchMetrics(patientId);
      setWatchMetrics(rows);
    } catch (error) {
      setWatchMetrics([]);
      handleError('Failed to load watchlist', error);
    } finally {
      setWatchMetricsLoading(false);
    }
  }, [patientId, isAuthenticated, handleError]);

  const loadMetricAlerts = useCallback(async () => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setMetricAlerts([]);
      return;
    }
    setMetricAlertsLoading(true);
    try {
      const rows = await api.listMetricAlerts(patientId);
      setMetricAlerts(rows);
    } catch (error) {
      setMetricAlerts([]);
      handleError('Failed to load metric alerts', error);
    } finally {
      setMetricAlertsLoading(false);
    }
  }, [patientId, isAuthenticated, handleError]);

  useEffect(() => {
    if (!isAuthenticated || !patientId || patientId <= 0) {
      setDataConnections([]);
      setDashboardHighlights(null);
      setWatchMetrics([]);
      setMetricAlerts([]);
      return;
    }
    void loadDashboardConnections();
    void loadDashboardHighlights();
    void loadWatchMetrics();
    void loadMetricAlerts();
  }, [
    isAuthenticated,
    patientId,
    loadDashboardConnections,
    loadDashboardHighlights,
    loadWatchMetrics,
    loadMetricAlerts,
  ]);

  const dashboardHighlightItems = useMemo(
    () => dashboardHighlights?.highlights ?? [],
    [dashboardHighlights],
  );

  useEffect(() => {
    if (!dashboardHighlightItems.length) {
      setSelectedMetricKey(null);
      setMetricDetail(null);
      return;
    }
    if (!selectedMetricKey || !dashboardHighlightItems.some((item) => item.metric_key === selectedMetricKey)) {
      setSelectedMetricKey(dashboardHighlightItems[0].metric_key);
    }
  }, [dashboardHighlightItems, selectedMetricKey]);

  useEffect(() => {
    if (!patientId || patientId <= 0 || !isAuthenticated || !selectedMetricKey) {
      setMetricDetail(null);
      return;
    }
    setMetricDetailLoading(true);
    api.getMetricDetail(patientId, selectedMetricKey)
      .then((result) => setMetricDetail(result))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 404) {
          setMetricDetail(null);
          return;
        }
        handleError('Failed to load metric details', error);
        setMetricDetail(null);
      })
      .finally(() => setMetricDetailLoading(false));
  }, [patientId, isAuthenticated, selectedMetricKey, handleError]);

  const handleConnectProvider = useCallback(async (providerName: string, providerSlug: string) => {
    if (!patientId || patientId <= 0) return;
    setActiveConnectionSlug(providerSlug);
    try {
      await api.upsertDataConnection(patientId, {
        provider_name: providerName,
        provider_slug: providerSlug,
        status: 'connected',
        is_active: true,
        last_error: null,
      });
      pushToast('success', `${providerName} connected.`);
      await loadDashboardConnections();
    } catch (error) {
      handleError('Failed to connect provider', error);
    } finally {
      setActiveConnectionSlug(null);
    }
  }, [patientId, loadDashboardConnections, pushToast, handleError]);

  const handleConnectionState = useCallback(async (connection: DataConnection) => {
    if (!patientId || patientId <= 0) return;
    setActiveConnectionSlug(connection.provider_slug);
    const nextActive = !connection.is_active;
    try {
      await api.upsertDataConnection(patientId, {
        provider_name: connection.provider_name,
        provider_slug: connection.provider_slug,
        status: nextActive ? 'connected' : 'disconnected',
        source_count: connection.source_count,
        is_active: nextActive,
        last_synced_at: connection.last_synced_at,
        last_error: nextActive ? null : connection.last_error,
      });
      pushToast('success', nextActive ? `${connection.provider_name} reconnected.` : `${connection.provider_name} disconnected.`);
      await loadDashboardConnections();
    } catch (error) {
      handleError('Failed to update connection status', error);
    } finally {
      setActiveConnectionSlug(null);
    }
  }, [patientId, loadDashboardConnections, pushToast, handleError]);

  const handleSyncConnection = useCallback(async (connection: DataConnection) => {
    if (!patientId || patientId <= 0) return;
    setActiveSyncConnectionId(connection.id);
    try {
      await api.markConnectionSynced(patientId, connection.id);
      pushToast('success', `${connection.provider_name} synced.`);
      await loadDashboardConnections();
    } catch (error) {
      handleError('Failed to sync connection', error);
    } finally {
      setActiveSyncConnectionId(null);
    }
  }, [patientId, loadDashboardConnections, pushToast, handleError]);

  const handleToggleSelectedWatchMetric = useCallback(async () => {
    if (!patientId || patientId <= 0 || !selectedMetricKey) return;
    const existing = watchMetrics.find((item) => item.metric_key === selectedMetricKey);
    setActiveWatchMetricId(existing?.id ?? -1);
    try {
      if (existing) {
        await api.deleteWatchMetric(patientId, existing.id);
        pushToast('success', `${existing.metric_name} removed from watchlist.`);
      } else {
        const fallbackLabel = selectedMetricKey.replace(/_/g, ' ');
        await api.upsertWatchMetric(patientId, {
          metric_name: metricDetail?.metric_name ?? fallbackLabel,
          metric_key: selectedMetricKey,
          lower_bound: metricDetail?.range_min ?? undefined,
          upper_bound: metricDetail?.range_max ?? undefined,
          direction: 'both',
          is_active: true,
        });
        pushToast('success', `${metricDetail?.metric_name ?? fallbackLabel} added to watchlist.`);
      }
      await loadWatchMetrics();
      await loadMetricAlerts();
    } catch (error) {
      handleError('Failed to update watchlist', error);
    } finally {
      setActiveWatchMetricId(null);
    }
  }, [
    patientId,
    selectedMetricKey,
    watchMetrics,
    metricDetail?.metric_name,
    metricDetail?.range_min,
    metricDetail?.range_max,
    loadWatchMetrics,
    loadMetricAlerts,
    pushToast,
    handleError,
  ]);

  const handleRemoveWatchMetric = useCallback(async (watchMetric: WatchMetric) => {
    if (!patientId || patientId <= 0) return;
    setActiveWatchMetricId(watchMetric.id);
    try {
      await api.deleteWatchMetric(patientId, watchMetric.id);
      pushToast('success', `${watchMetric.metric_name} removed from watchlist.`);
      await loadWatchMetrics();
      await loadMetricAlerts();
    } catch (error) {
      handleError('Failed to remove watch metric', error);
    } finally {
      setActiveWatchMetricId(null);
    }
  }, [patientId, loadWatchMetrics, loadMetricAlerts, pushToast, handleError]);

  const handleEvaluateAlerts = useCallback(async () => {
    if (!patientId || patientId <= 0) return;
    setAlertsEvaluating(true);
    try {
      const result = await api.evaluateMetricAlerts(patientId);
      if (result.generated > 0) {
        pushToast('success', `${result.generated} new alert${result.generated === 1 ? '' : 's'} generated.`);
      } else {
        pushToast('info', 'No new alerts generated.');
      }
      await loadMetricAlerts();
    } catch (error) {
      handleError('Failed to evaluate alerts', error);
    } finally {
      setAlertsEvaluating(false);
    }
  }, [patientId, loadMetricAlerts, pushToast, handleError]);

  const handleAcknowledgeAlert = useCallback(async (alertId: number) => {
    if (!patientId || patientId <= 0) return;
    setActiveAlertId(alertId);
    try {
      await api.acknowledgeMetricAlert(patientId, alertId);
      pushToast('success', 'Alert acknowledged.');
      await loadMetricAlerts();
    } catch (error) {
      handleError('Failed to acknowledge alert', error);
    } finally {
      setActiveAlertId(null);
    }
  }, [patientId, loadMetricAlerts, pushToast, handleError]);

  const loadAccessRequests = useCallback(async () => {
    if (!isAuthenticated) return;
    setAccessRequestsLoading(true);
    try {
      const list = await api.listPatientAccessRequests();
      setAccessRequests(list);
    } catch {
      setAccessRequests([]);
    } finally {
      setAccessRequestsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      void loadAccessRequests();
    }
  }, [isAuthenticated, loadAccessRequests]);

  const handleApproveAccess = useCallback(async (grantId: number) => {
    setActingGrantId(grantId);
    try {
      await api.patientAccessGrant({ grant_id: grantId });
      pushToast('success', 'Access approved. The clinician can now view this profile.');
      await loadAccessRequests();
    } catch (error) {
      handleError('Failed to approve access', error);
    } finally {
      setActingGrantId(null);
    }
  }, [pushToast, loadAccessRequests, handleError]);

  const handleDenyAccess = useCallback(async (grantId: number) => {
    setActingGrantId(grantId);
    try {
      await api.patientAccessRevoke({ grant_id: grantId });
      pushToast('success', 'Access request denied.');
      await loadAccessRequests();
    } catch (error) {
      handleError('Failed to deny access', error);
    } finally {
      setActingGrantId(null);
    }
  }, [pushToast, loadAccessRequests, handleError]);

  useEffect(() => {
    if (isAuthenticated) {
      api.checkOcrAvailability()
        .then((result) => setOcrAvailable(result.available))
        .catch(() => setOcrAvailable(null));
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (latestDocumentId && isAuthenticated) {
      api.getDocumentStatus(latestDocumentId)
        .then((status) => {
          setLatestDocumentStatus({
            chunks: status.chunks,
            processing_status: status.processing_status,
            processing_error: status.processing_error,
          });
        })
        .catch(() => setLatestDocumentStatus(null));
    } else {
      setLatestDocumentStatus(null);
    }
  }, [latestDocumentId, isAuthenticated]);

  const dashboardSummary = dashboardHighlights?.summary ?? null;
  const selectedWatchMetric = useMemo(
    () => watchMetrics.find((item) => item.metric_key === selectedMetricKey) ?? null,
    [watchMetrics, selectedMetricKey],
  );
  const activeAlertsCount = useMemo(
    () => metricAlerts.filter((alert) => !alert.acknowledged).length,
    [metricAlerts],
  );

  return {
    insights,
    insightsLoading,
    dashboardHighlightItems,
    dashboardSummary,
    dashboardHighlightsLoading,
    selectedMetricKey,
    setSelectedMetricKey,
    metricDetail,
    metricDetailLoading,
    watchMetrics,
    watchMetricsLoading,
    selectedWatchMetric,
    metricAlerts,
    metricAlertsLoading,
    activeAlertsCount,
    alertsEvaluating,
    activeWatchMetricId,
    activeAlertId,
    dashboardConnectionLoading,
    dataConnections,
    activeConnectionSlug,
    activeSyncConnectionId,
    ocrAvailable,
    latestDocumentStatus,
    accessRequests,
    accessRequestsLoading,
    actingGrantId,
    handleConnectProvider,
    handleConnectionState,
    handleSyncConnection,
    handleToggleSelectedWatchMetric,
    handleRemoveWatchMetric,
    handleEvaluateAlerts,
    handleAcknowledgeAlert,
    handleApproveAccess,
    handleDenyAccess,
  };
};

export default useDashboardData;
