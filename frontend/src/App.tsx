import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import { ApiError, api, buildBackendUrl } from './api';
import useToast from './hooks/useToast';
import useAppStore from './store/useAppStore';
import usePatients from './hooks/usePatients';
import usePatientRecords from './hooks/usePatientRecords';
import usePatientDocuments from './hooks/usePatientDocuments';
import useChat from './hooks/useChat';
import useDocumentUpload from './hooks/useDocumentUpload';
import useAppErrorHandler from './hooks/useAppErrorHandler';
import useDashboardData from './hooks/useDashboardData';
import useDocumentWorkspace from './hooks/useDocumentWorkspace';
import useChatUploads from './hooks/useChatUploads';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';
import ToastStack from './components/ToastStack';
import HeroSection from './components/HeroSection';
import DocumentsPanel from './components/DocumentsPanel';
import RecordsPanel from './components/RecordsPanel';
import ChatInterface from './components/ChatInterface';
import LocalizationModal from './components/LocalizationModal';
import AlertsPanel from './components/dashboard/AlertsPanel';
import ClinicianAccessPanel from './components/dashboard/ClinicianAccessPanel';
import ConnectionsPanel from './components/dashboard/ConnectionsPanel';
import FocusAreasPanel from './components/dashboard/FocusAreasPanel';
import HighlightsPanel from './components/dashboard/HighlightsPanel';
import MetricDetailPanel from './components/dashboard/MetricDetailPanel';
import TrendsPanel from './components/dashboard/TrendsPanel';
import WatchlistPanel from './components/dashboard/WatchlistPanel';
import ClinicianApp from './pages/ClinicianApp';
import type { PatientSummary } from './types';

const defaultHighlights = [
  { title: 'LDL Cholesterol', value: '167 mg/dL', trend: 'down', note: 'Jun 2025' },
  { title: 'Omega-3', value: '4.5%', trend: 'down', note: 'Jun 2025' },
  { title: 'Vitamin D', value: '26 ng/mL', trend: 'down', note: 'Jun 2025' },
  { title: 'Hemoglobin A1C', value: '5.4%', trend: 'flat', note: 'Jun 2025' },
];

const a1cSeries = [6.1, 5.9, 5.8, 5.6, 5.5, 5.4];

const suggestedProviders: Array<{ provider_name: string; provider_slug: string }> = [
  { provider_name: 'Sutter Health', provider_slug: 'sutter_health' },
  { provider_name: 'Kaiser Permanente', provider_slug: 'kaiser_permanente' },
  { provider_name: 'Quest Diagnostics', provider_slug: 'quest_diagnostics' },
  { provider_name: 'UCSF Medical', provider_slug: 'ucsf_medical' },
  { provider_name: 'Function Health', provider_slug: 'function_health' },
  { provider_name: 'Stanford Medical', provider_slug: 'stanford_medical' },
  { provider_name: 'Cedars-Sinai', provider_slug: 'cedars_sinai' },
  { provider_name: 'One Medical', provider_slug: 'one_medical' },
  { provider_name: 'GoodRx', provider_slug: 'goodrx' },
];

type BackendStatus = 'checking' | 'online' | 'offline';

const buildPath = (values: number[]) => {
  if (!values.length) return '';
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = 20 + index * 56;
      const y = 60 - ((value - min) / span) * 40;
      return `${index === 0 ? 'M' : 'L'}${x} ${y}`;
    })
    .join(' ');
};

const buildScaledPath = (values: number[], width = 320, height = 90) => {
  if (!values.length) return '';
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const xPadding = 18;
  const yPadding = 14;
  const step = (width - xPadding * 2) / Math.max(values.length - 1, 1);
  return values
    .map((value, index) => {
      const x = xPadding + index * step;
      const y = height - yPadding - ((value - min) / span) * (height - yPadding * 2);
      return `${index === 0 ? 'M' : 'L'}${x} ${y}`;
    })
    .join(' ');
};

const formatNumber = (value: number) => {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, '');
};

const formatMetricReading = (
  value: string | null | undefined,
  numericValue: number | null | undefined,
  unit: string | null | undefined,
) => {
  const base = value?.trim()
    ? value.trim()
    : typeof numericValue === 'number'
      ? formatNumber(numericValue)
      : '—';
  return unit ? `${base} ${unit}` : base;
};

function App() {
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '';
  if (pathname.startsWith('/clinician')) {
    return <ClinicianApp />;
  }
  return <PatientApp />;
}

function PatientApp() {
  const patientId = useAppStore((state) => state.patientId);
  const patientSearch = useAppStore((state) => state.patientSearch);
  const accessToken = useAppStore((state) => state.accessToken);
  const currentUser = useAppStore((state) => state.user);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const isClinician = useAppStore((state) => state.isClinician);
  const setAccessToken = useAppStore((state) => state.setAccessToken);
  const setUser = useAppStore((state) => state.setUser);
  const setPatientIdStore = useAppStore((state) => state.setPatientId);
  const setPatientSearch = useAppStore((state) => state.setPatientSearch);
  const setPatientId = useCallback((id: number | null) => {
    setPatientIdStore(id ?? 0);
  }, [setPatientIdStore]);
  const [formData, setFormData] = useState({ title: '', content: '', record_type: 'general' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [patientLoadingFailed, setPatientLoadingFailed] = useState(false);
  const [autoSelectedPatient, setAutoSelectedPatient] = useState<PatientSummary | null>(null);
  const [profileSummary, setProfileSummary] = useState<{
    id: number;
    is_dependent: boolean;
    profile_completion?: { overall_percentage: number };
  } | null>(null);
  const [primaryPatientId, setPrimaryPatientId] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'chat' | 'dashboard'>('chat');
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');
  const { toasts, pushToast } = useToast();
  const previousBackendStatusRef = useRef<BackendStatus>('checking');
  const { handleError, clearBanner } = useAppErrorHandler({
    setBanner: setErrorBanner,
    pushToast,
  });
  const clearErrorBanner = clearBanner;
  const clearErrorBannerOnRecordsSuccess = useCallback(() => {
    setErrorBanner(null);
  }, []);

  useEffect(() => {
    if (
      isAuthenticated &&
      isClinician &&
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/clinician')
    ) {
      window.location.href = '/clinician';
    }
  }, [isAuthenticated, isClinician]);


  const { patients, isLoading: patientLoading, reload: reloadPatients, hasLoadedSuccessfully } = usePatients({
    search: patientSearch,
    isAuthenticated,
    onError: handleError,
  });
  const {
    records,
    isLoading: recordsLoading,
    reloadRecords,
  } = usePatientRecords({
    patientId,
    onError: handleError,
    onSuccess: clearErrorBannerOnRecordsSuccess,
  });
  const {
    documents,
    isLoading: documentsLoading,
    reloadDocuments,
  } = usePatientDocuments({ patientId, isAuthenticated, onError: handleError, onSuccess: clearErrorBanner });
  const { messages, question, setQuestion, isStreaming, send, sendVision, sendVolume, sendWsi, pushMessage } = useChat({
    patientId,
    onError: handleError,
  });
  const { uploadWithDuplicateCheck } = useDocumentUpload(patientId);

  const documentWorkspace = useDocumentWorkspace({
    patientId,
    documents,
    reloadDocuments,
    uploadWithDuplicateCheck,
    pushToast,
    handleError,
  });

  const {
    localizationPreview,
    handleChatUpload,
    handleLocalizeUpload,
    clearLocalizationPreview,
  } = useChatUploads({
    patientId,
    question,
    setQuestion,
    reloadDocuments,
    uploadWithDuplicateCheck,
    pushToast,
    handleError,
    sendVision,
    sendVolume,
    sendWsi,
    pushMessage,
  });

  // Compute selectedPatient early so it can be used in useEffect hooks
  // Only use autoSelectedPatient if it matches the current patientId
  const selectedPatient = useMemo(
    () => {
      if (autoSelectedPatient && autoSelectedPatient.id === patientId) {
        return autoSelectedPatient;
      }
      return patients.find((patient) => patient.id === patientId) || null;
    },
    [autoSelectedPatient, patients, patientId]
  );

  const requestOpenProfile = useCallback(() => {
    if (typeof window === 'undefined') return;
    const targetId = selectedPatient?.id ?? patientId ?? undefined;
    window.dispatchEvent(new CustomEvent('medmemory:open-profile', { detail: { patientId: targetId } }));
  }, [selectedPatient, patientId]);

  useEffect(() => {
    let cancelled = false;
    let retryTimerId: number | undefined;

    const retryDelaysMs = [0, 1500, 5000];

    const runHealthCheckWithRetry = (attempt: number) => {
      retryTimerId = window.setTimeout(async () => {
        try {
          await api.getHealth();
          if (!cancelled) {
            setBackendStatus('online');
          }
        } catch {
          if (cancelled) return;
          if (attempt < retryDelaysMs.length - 1) {
            runHealthCheckWithRetry(attempt + 1);
            return;
          }
          setBackendStatus('offline');
        }
      }, retryDelaysMs[attempt]);
    };

    runHealthCheckWithRetry(0);
    const pollTimerId = window.setInterval(() => runHealthCheckWithRetry(0), 45000);

    return () => {
      cancelled = true;
      if (retryTimerId) window.clearTimeout(retryTimerId);
      window.clearInterval(pollTimerId);
    };
  }, []);

  useEffect(() => {
    const previousStatus = previousBackendStatusRef.current;
    if (backendStatus === previousStatus) return;
    if (!isAuthenticated) {
      previousBackendStatusRef.current = backendStatus;
      return;
    }

    if (backendStatus === 'offline') {
      pushToast('info', 'Backend is temporarily unavailable. Some actions may fail.');
    } else if (backendStatus === 'online' && previousStatus === 'offline') {
      pushToast('success', 'Backend connection restored.');
    }
    previousBackendStatusRef.current = backendStatus;
  }, [backendStatus, isAuthenticated, pushToast]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (event.key !== '/') return;
      if (
        event.target instanceof HTMLElement &&
        (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA')
      ) {
        return;
      }
      const input = document.getElementById('patient-search') as HTMLInputElement | null;
      if (input) {
        event.preventDefault();
        input.focus();
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);

  useEffect(() => {
    if (!accessToken || currentUser) return;
    api
      .getCurrentUser()
      .then((user) => {
        setUser(user);
      })
      .catch((error) => {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          setAccessToken(null);
          handleError('Session expired', error);
        } else {
          handleError('Connection issue', error);
        }
      });
  }, [accessToken, currentUser, setAccessToken, setUser, handleError]);

  // Verify patient exists when patientId is set but not found in loaded patients list
  useEffect(() => {
    if (!currentUser || !accessToken || !patientId || patientId <= 0) return;
    if (patientLoading || selectedPatient || !hasLoadedSuccessfully) return;
    if (patientSearch.trim().length > 0) return;

    const patientExists = patients.some((p) => p.id === patientId);
    if (!patientExists && patients.length > 0) {
      console.warn('Patient ID does not exist in patient list, clearing it');
      setPatientId(0);
    }
  }, [
    currentUser,
    accessToken,
    patientId,
    selectedPatient,
    patients,
    patientLoading,
    patientSearch,
    hasLoadedSuccessfully,
    setPatientId,
  ]);

  // Auto-select or create patient when user logs in
  useEffect(() => {
    if (!currentUser || !accessToken || patientId > 0) {
      setPatientLoadingFailed(false);
      return;
    }
    
    let cancelled = false;
    setPatientLoadingFailed(false);
    
    const maxWaitTimeout = setTimeout(() => {
      if (cancelled || patientId > 0) return;
      console.error('Patient loading timeout');
      setPatientLoadingFailed(true);
      handleError('Loading timeout', new Error('Patient profile loading is taking too long. Please refresh the page.'));
    }, 15000);
    
    const timeoutId = setTimeout(() => {
      if (cancelled) return;
      
      const token = window.localStorage.getItem('medmemory_access_token');
      if (!token) {
        console.error('Access token not found');
        setPatientLoadingFailed(true);
        handleError('Authentication error', new Error('Access token missing'));
        clearTimeout(maxWaitTimeout);
        return;
      }
      
      console.log('Loading patient profile...');
      
      api.listPatients()
        .then((patientList) => {
          if (cancelled) return;
          clearTimeout(maxWaitTimeout);
          console.log('Patient list loaded:', patientList);
          
          if (patientList.length > 0) {
            console.log('Selecting patient:', patientList[0].id);
            setPatientId(patientList[0].id);
            setAutoSelectedPatient(patientList[0]);
            setPatientLoadingFailed(false);
          } else {
            console.log('Creating new patient profile...');
            const nameParts = currentUser.full_name.split(' ');
            const firstName = nameParts[0] || currentUser.email.split('@')[0];
            const lastName = nameParts.slice(1).join(' ') || 'User';
            api.createPatient({
                first_name: firstName,
                last_name: lastName,
                email: currentUser.email,
              })
              .then((newPatient) => {
                if (cancelled) return;
                console.log('Patient created:', newPatient);
                setPatientId(newPatient.id);
                setAutoSelectedPatient(newPatient);
                setPatientLoadingFailed(false);
                pushToast('success', 'Your medical profile has been created.');
              })
              .catch((error) => {
                if (cancelled) return;
                clearTimeout(maxWaitTimeout);
                console.error('Failed to create patient:', error);
                setPatientLoadingFailed(true);
                handleError('Failed to create patient profile', error);
              });
          }
        })
        .catch((error) => {
          if (cancelled) return;
          clearTimeout(maxWaitTimeout);
          console.error('Failed to load patient profile:', error);
          setPatientLoadingFailed(true);
          handleError('Failed to load patient profile', error);
        });
    }, 100);
    
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
      clearTimeout(maxWaitTimeout);
    };
  }, [currentUser, accessToken, patientId, setPatientId, handleError, pushToast]);

  useEffect(() => {
    if (!autoSelectedPatient) return;
    const exists = patients.some((patient) => patient.id === autoSelectedPatient.id);
    if (exists) {
      setAutoSelectedPatient(null);
    }
  }, [patients, autoSelectedPatient]);

  // Load primary patient ID on authentication (for "Back to My Health" functionality)
  useEffect(() => {
    if (!isAuthenticated) {
      setPrimaryPatientId(null);
      return;
    }
    let cancelled = false;
    api
      .getAuthHeaders()
      .then((headers) => fetch(buildBackendUrl('/api/v1/profile'), { headers }))
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load primary profile');
        const data = await res.json();
        if (cancelled) return;
        if (typeof data.id === 'number') {
          setPrimaryPatientId(data.id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !patientId) {
      setProfileSummary(null);
      return;
    }
    let cancelled = false;
    api
      .getAuthHeaders()
      .then((headers) =>
        fetch(buildBackendUrl(`/api/v1/profile?patient_id=${patientId}`), { headers })
      )
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load profile summary');
        const data = await res.json();
        if (cancelled) return;
        setProfileSummary({
          id: data.id,
          is_dependent: !!data.is_dependent,
          profile_completion: data.profile_completion,
        });
      })
      .catch(() => {
        if (!cancelled) setProfileSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, patientId]);

  // Document preview reset is handled by useDocumentWorkspace hook

  useEffect(() => {
    if (!patientId || selectedPatient || !isAuthenticated) return;
    api
      .getPatient(patientId)
      .then((patient) => {
        setAutoSelectedPatient(patient);
      })
      .catch(() => {});
  }, [patientId, selectedPatient, isAuthenticated]);

  const {
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
  } = useDashboardData({
    patientId,
    isAuthenticated,
    hasSelectedPatient: Boolean(selectedPatient),
    hasCurrentUser: Boolean(currentUser),
    latestDocumentId: documents[0]?.id,
    setPatientId,
    handleError,
    pushToast,
  });

  const handleAskQuestionFromDashboard = useCallback(() => {
    setViewMode('chat');
  }, []);

  const handleAskSelectedMetricInChat = useCallback(() => {
    if (!metricDetail) return;
    setViewMode('chat');
    send(
      `Summarize ${metricDetail.metric_name} using only patient records. Include latest value, reference range, and whether it is in or out of range. If evidence is missing, say you do not know.`,
    );
  }, [metricDetail, send]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.content.trim()) return;

    setIsSubmitting(true);
    try {
      await api.createRecord(patientId, {
        ...formData,
        title: formData.title.trim(),
        content: formData.content.trim(),
      });
      setFormData({ title: '', content: '', record_type: 'general' });
      pushToast('success', 'Record saved successfully.');
      await reloadRecords();
    } catch (error) {
      handleError('Failed to create record', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDependentAdded = useCallback((dependentId: number, dependentName: string) => {
    pushToast('success', `${dependentName} has been added to your family.`);
    setTimeout(() => {
      pushToast('info', `Upload ${dependentName}'s medical records to start tracking their health.`);
    }, 1500);
    reloadPatients();
    setAutoSelectedPatient({ id: dependentId, full_name: dependentName });
  }, [pushToast, reloadPatients]);

  const handleUploadDocument = async () => {
    await documentWorkspace.handleUpload();
  };


  const formatDate = useCallback((dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }, []);

  const recordCount = useMemo(() => records.length, [records.length]);
  const showDashboard = isAuthenticated && viewMode === 'dashboard';
  const processedDocs = useMemo(
    () => documents.filter((doc) => doc.is_processed).length,
    [documents],
  );
  const latestDocument = documents[0];
  const latestRecord = records[0];
  const a1cSeriesData = insights?.a1c_series?.length ? insights.a1c_series : a1cSeries;
  const a1cSeriesPath = useMemo(() => buildPath(a1cSeriesData), [a1cSeriesData]);
  const recentLabs = insights?.recent_labs ?? [];
  const activeMedications = insights?.active_medications ?? 0;
  const recentMedicationSummary = insights?.recent_medications?.[0]
    ? `${insights.recent_medications[0].name} · ${insights.recent_medications[0].dosage || 'dose'}`
    : 'Add medications to track adherence signals.';
  const handleSummarizeLatestDocumentInChat = useCallback(() => {
    if (!latestDocument) return;
    setViewMode('chat');
    send(
      'Summarize the most recent document using only values explicitly shown. Use short, friendly sentences. Do not infer meanings or add follow-ups. If no numeric values are shown, say so in one sentence.',
    );
  }, [latestDocument, send]);
  const handleReviewLatestRecordInChat = useCallback(() => {
    if (!latestRecord) return;
    setViewMode('chat');
    const recordName = latestRecord.title || 'my latest record';
    send(
      `Please review the record "${recordName}" and summarize only what is explicitly stated. Do not add recommendations unless they are listed in the record.`,
    );
  }, [latestRecord, send]);
  // highlightItems can be used for a summary strip in the future
  const _highlightItems = useMemo(() => {
    if (!insights?.recent_labs?.length) return defaultHighlights;
    return insights.recent_labs.map((lab) => ({
      title: lab.test_name,
      value: `${lab.value || '—'} ${lab.unit || ''}`.trim(),
      trend: lab.is_abnormal ? 'down' : 'flat',
      note: lab.collected_at ? formatDate(lab.collected_at) : 'Latest',
    }));
  }, [insights, formatDate]);
  void _highlightItems; // Suppress unused warning - reserved for future use

  const localizationModal = localizationPreview ? (
    <LocalizationModal
      imageUrl={localizationPreview.imageUrl}
      boxes={localizationPreview.boxes}
      onClose={clearLocalizationPreview}
    />
  ) : null;
  const insightSummary = useMemo(() => {
    if (!insights) return 'Connect lab results and medications to unlock insights.';
    if (!insights.lab_total && !insights.active_medications) {
      return 'No lab or medication data yet. Add data to see trends.';
    }
    if (insights.lab_total && insights.lab_abnormal) {
      return `${insights.lab_abnormal} abnormal result${insights.lab_abnormal === 1 ? '' : 's'} across ${insights.lab_total} labs.`;
    }
    if (insights.lab_total) {
      return `${insights.lab_total} labs recorded. No abnormal results flagged.`;
    }
    return `${insights.active_medications} active medication${insights.active_medications === 1 ? '' : 's'} on file.`;
  }, [insights]);
  const insightCards = useMemo(() => ([
    {
      title: 'Records',
      value: recordCount,
      note: recordCount ? `${recordCount} clinical note${recordCount === 1 ? '' : 's'}` : 'Add clinical notes',
      icon: '📝',
    },
    {
      title: 'Documents',
      value: documents.length,
      note: documents.length ? `${processedDocs} ready for Q&A` : 'Upload lab reports',
      icon: '📋',
    },
    {
      title: 'AI Signals',
      value: processedDocs,
      note: processedDocs ? 'MedGemma analyzed' : 'Upload to analyze',
      icon: '🧠',
    },
  ]), [recordCount, documents.length, processedDocs]);
  const availableProviders = useMemo(
    () =>
      suggestedProviders.filter(
        (provider) => !dataConnections.some((connection) => connection.provider_slug === provider.provider_slug),
      ),
    [dataConnections],
  );
  const metricTrendValues = useMemo(
    () =>
      metricDetail?.trend
        .map((point) => point.value)
        .filter((value): value is number => typeof value === 'number') ?? [],
    [metricDetail],
  );
  const metricTrendPath = useMemo(
    () => (metricTrendValues.length > 1 ? buildScaledPath(metricTrendValues) : ''),
    [metricTrendValues],
  );

  // Only show viewing banner when viewing a dependent's profile
  const viewingBanner = selectedPatient && profileSummary?.is_dependent ? (
    <div className="viewing-dependent-banner">
      <div className="viewing-dependent-info">
        <span className="viewing-dependent-icon">👶</span>
        <span className="viewing-dependent-name">Viewing: {selectedPatient.full_name}</span>
        {selectedPatient.age != null && (
          <span className="viewing-dependent-age">(Age {selectedPatient.age})</span>
        )}
      </div>
      <div className="viewing-dependent-actions">
        <button type="button" onClick={requestOpenProfile}>
          Edit Profile
        </button>
        {primaryPatientId && (
          <button type="button" onClick={() => setPatientId(primaryPatientId)}>
            Back to My Health
          </button>
        )}
      </div>
    </div>
  ) : null;

  const profileCompletionPct = profileSummary?.profile_completion?.overall_percentage;
  const showProfileCta = typeof profileCompletionPct === 'number' && profileCompletionPct < 80;
  const offlineWarning = backendStatus === 'offline'
    ? 'Backend is currently unavailable. Sign in, chat, uploads, and sync may fail until service is restored.'
    : null;
  const authenticatedBanner = errorBanner || offlineWarning;
  const landingBanner = errorBanner || offlineWarning;

  if (isAuthenticated && isClinician) {
    return null;
  }

  if (!isAuthenticated) {
    return (
      <div className="app-shell landing">
        <TopBar backendStatus={backendStatus} />
        <ErrorBanner message={landingBanner} />
        <main className="landing-main">
          <HeroSection
            selectedPatient={selectedPatient ?? undefined}
            isLoading={patientLoading}
            patients={patients}
            searchValue={patientSearch}
            isSearchLoading={patientLoading}
            selectedPatientId={patientId}
            onSearchChange={setPatientSearch}
            onSelectPatient={(id) => setPatientId(id)}
            isAuthenticated={isAuthenticated}
            backendStatus={backendStatus}
          />
        </main>
        <ToastStack toasts={toasts} />
        {localizationModal}
      </div>
    );
  }

  const isLoadingPatient = patientId === 0 && isAuthenticated && currentUser && !patientLoadingFailed;
  
  if (isLoadingPatient) {
    return (
      <div className="app-shell chat-mode">
        <TopBar
          backendStatus={backendStatus}
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={authenticatedBanner} />
        <div className="chat-loading-state">
          <div className="loading-spinner" />
          <p>Setting up your medical profile...</p>
          <p className="loading-hint">This may take a few moments...</p>
        </div>
        <ToastStack toasts={toasts} />
        {localizationModal}
      </div>
    );
  }
  
  if (!selectedPatient && isAuthenticated && currentUser && patientLoadingFailed) {
    return (
      <div className="app-shell chat-mode">
        <TopBar
          backendStatus={backendStatus}
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={errorBanner || offlineWarning || 'Unable to load your medical profile. Please refresh the page.'} />
        <div className="chat-error-state">
          <h2>Unable to Load Profile</h2>
          <p>There was an issue setting up your medical profile. Please try:</p>
          <ul>
            <li>Make sure the backend is running: <code>cd backend && uvicorn app.main:app --reload --port 8000</code></li>
            <li>Make sure the frontend dev server is running: <code>cd frontend && npm run dev</code></li>
            <li>The frontend should be on <code>http://127.0.0.1:5174</code> (not a production build)</li>
            <li>Check the browser console (F12) for detailed error messages</li>
            <li>Try refreshing the page</li>
          </ul>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button 
              className="primary-button" 
              onClick={() => {
                setPatientLoadingFailed(false);
                window.location.reload();
              }}
              type="button"
            >
              Refresh Page
            </button>
            <button 
              className="secondary-button" 
              onClick={() => {
                // Open backend health check in new tab
                window.open('http://localhost:8000/health', '_blank');
              }}
              type="button"
            >
              Test Backend
            </button>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '1rem' }}>
            <strong>Debug info:</strong> Check the browser console (F12 → Console) for detailed API request logs.
          </p>
        </div>
        <ToastStack toasts={toasts} />
        {localizationModal}
      </div>
    );
  }

  if (showDashboard) {
    return (
      <div className="app-shell dashboard-mode">
        <TopBar
          backendStatus={backendStatus}
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={authenticatedBanner} />
        <main className="dashboard">
          {viewingBanner}
          <div className="dashboard-header">
            <div>
              <p className="eyebrow">Patient overview</p>
              <h1>
                {selectedPatient?.full_name || 'Your health dashboard'}
              </h1>
              <p className="subtitle">
                Track records, documents, and insights in one place.
              </p>
            </div>
            <div className="insight-card primary">
              <h3>
                {documents.length || recordCount
                  ? 'Insight snapshot'
                  : 'Welcome to MedMemory'}
              </h3>
              <p>
                {documents.length || recordCount
                  ? 'Your data is ready. Ask questions or view trends below.'
                  : 'Your AI-powered medical memory. Upload documents to get started.'}
              </p>
              <span className="insight-pill">
                {processedDocs 
                  ? `${processedDocs} source${processedDocs === 1 ? '' : 's'} • MedGemma ready` 
                  : 'Powered by MedGemma AI'}
              </span>
            </div>
          </div>
          {showProfileCta ? (
            <div className="profile-cta">
              <div>
                <h3>
                  {profileSummary?.is_dependent && selectedPatient
                    ? `Complete ${selectedPatient.full_name}'s health profile`
                    : 'Complete your health profile'}
                </h3>
                <p>
                  {profileSummary?.is_dependent && selectedPatient
                    ? `${selectedPatient.full_name}'s profile is ${profileCompletionPct}% complete. Add medical history and providers for better insights.`
                    : `You're ${profileCompletionPct}% complete. Add providers and lifestyle details for more personal insights.`}
                </p>
              </div>
              <button className="primary-button" type="button" onClick={requestOpenProfile}>
                {profileSummary?.is_dependent ? 'Complete profile' : 'Finish profile'}
              </button>
            </div>
          ) : null}
          <div className="insight-strip">
            {insightCards.map((card) => (
              <div className="insight-card" key={card.title}>
                <div className="insight-card-header">
                  <span className="insight-icon">{card.icon}</span>
                  <h4>{card.title}</h4>
                </div>
                <p className="insight-value">{card.value}</p>
                <span className="insight-note">{card.note}</span>
              </div>
            ))}
          </div>
          <section className="dashboard-main dashboard-main-data">
            <ConnectionsPanel
              loading={dashboardConnectionLoading}
              connections={dataConnections}
              availableProviders={availableProviders}
              activeConnectionSlug={activeConnectionSlug}
              activeSyncConnectionId={activeSyncConnectionId}
              onConnectProvider={handleConnectProvider}
              onToggleConnection={handleConnectionState}
              onSyncConnection={handleSyncConnection}
              formatDate={formatDate}
            />
            <HighlightsPanel
              loading={dashboardHighlightsLoading}
              summary={dashboardSummary}
              items={dashboardHighlightItems}
              selectedMetricKey={selectedMetricKey}
              onSelectMetric={setSelectedMetricKey}
              formatDate={formatDate}
              formatMetricReading={formatMetricReading}
              formatNumber={formatNumber}
            />
          </section>
          <ClinicianAccessPanel
            patientId={patientId}
            accessRequestsLoading={accessRequestsLoading}
            accessRequests={accessRequests}
            actingGrantId={actingGrantId}
            onApproveAccess={handleApproveAccess}
            onDenyAccess={handleDenyAccess}
          />
          <section className="dashboard-main dashboard-main-metrics">
            <MetricDetailPanel
              metricDetail={metricDetail}
              metricDetailLoading={metricDetailLoading}
              selectedMetricKey={selectedMetricKey}
              selectedWatchMetric={selectedWatchMetric}
              activeWatchMetricId={activeWatchMetricId}
              metricTrendPath={metricTrendPath}
              onToggleWatchMetric={handleToggleSelectedWatchMetric}
              onAskInChat={handleAskSelectedMetricInChat}
              formatDate={formatDate}
              formatMetricReading={formatMetricReading}
            />
            <div className="metric-side-stack">
              <WatchlistPanel
                watchMetricsLoading={watchMetricsLoading}
                watchMetrics={watchMetrics}
                activeWatchMetricId={activeWatchMetricId}
                onRemoveWatchMetric={handleRemoveWatchMetric}
              />
              <AlertsPanel
                metricAlertsLoading={metricAlertsLoading}
                metricAlerts={metricAlerts}
                activeAlertsCount={activeAlertsCount}
                alertsEvaluating={alertsEvaluating}
                activeAlertId={activeAlertId}
                onEvaluateAlerts={handleEvaluateAlerts}
                onAcknowledgeAlert={handleAcknowledgeAlert}
                formatDate={formatDate}
                formatMetricReading={formatMetricReading}
              />
            </div>
          </section>
          <section className="dashboard-main">
            <TrendsPanel
              hasDocuments={documents.length > 0}
              insightsLoading={insightsLoading}
              insightSummary={insightSummary}
              recentLabs={recentLabs}
              a1cPath={a1cSeriesPath}
              onAskQuestion={handleAskQuestionFromDashboard}
              formatDate={formatDate}
            />
            <FocusAreasPanel
              latestDocument={latestDocument}
              latestDocumentStatus={latestDocumentStatus}
              latestRecord={latestRecord}
              ocrAvailable={ocrAvailable}
              activeMedications={activeMedications}
              recentMedicationSummary={recentMedicationSummary}
              onSummarizeLatestDocument={handleSummarizeLatestDocumentInChat}
              onReviewLatestRecord={handleReviewLatestRecordInChat}
              formatDate={formatDate}
            />
          </section>
          <section className="dashboard-workspace">
            <DocumentsPanel
              documents={documents}
              isLoading={documentsLoading}
              processingIds={documentWorkspace.processingIds}
              deletingIds={documentWorkspace.deletingIds}
              selectedFile={documentWorkspace.selectedFile}
              status={documentWorkspace.status}
              preview={documentWorkspace.preview}
              downloadUrl={documentWorkspace.downloadUrl}
              isDisabled={!selectedPatient}
              selectedPatient={selectedPatient ? {
                full_name: selectedPatient.full_name,
                is_dependent: profileSummary?.is_dependent,
              } : null}
              onFileChange={documentWorkspace.setSelectedFile}
              onUpload={handleUploadDocument}
              onProcess={documentWorkspace.handleProcess}
              onView={documentWorkspace.handleView}
              onDelete={documentWorkspace.handleDelete}
              onClosePreview={documentWorkspace.handleClosePreview}
            />
            <RecordsPanel
              records={records}
              isLoading={recordsLoading}
              recordCount={recordCount}
              formData={formData}
              isSubmitting={isSubmitting}
              isDisabled={!selectedPatient}
              onFormChange={(field, value) => setFormData((prev) => ({ ...prev, [field]: value }))}
              onSubmit={handleSubmit}
              formatDate={formatDate}
            />
          </section>
        </main>
        <ToastStack toasts={toasts} />
        {localizationModal}
      </div>
    );
  }

  return (
    <div className="app-shell chat-mode">
      <TopBar
        backendStatus={backendStatus}
        viewMode={viewMode}
        onViewChange={setViewMode}
        patientMeta={selectedPatient}
        selectedPatientId={patientId}
        onPatientChange={setPatientId}
        onDependentAdded={handleDependentAdded}
      />
      <ErrorBanner message={authenticatedBanner} />
      {viewingBanner}
      <ChatInterface
        messages={messages}
        question={question}
        isStreaming={isStreaming}
        isDisabled={!patientId}
        selectedPatient={selectedPatient ? {
          ...selectedPatient,
          is_dependent: profileSummary?.is_dependent,
        } : undefined}
        showHeader={false}
        onQuestionChange={setQuestion}
        onSend={send}
        onUploadFile={handleChatUpload}
        onLocalizeFile={handleLocalizeUpload}
      />
      <ToastStack toasts={toasts} />
      {localizationModal}
    </div>
  );
}

export default App;
