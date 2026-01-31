import { useCallback, useEffect, useMemo, useState } from 'react';
import './App.css';
import { ApiError, api } from './api';
import useToast from './hooks/useToast';
import useAppStore from './store/useAppStore';
import usePatients from './hooks/usePatients';
import usePatientRecords from './hooks/usePatientRecords';
import usePatientDocuments from './hooks/usePatientDocuments';
import useChat from './hooks/useChat';
import useDocumentUpload from './hooks/useDocumentUpload';
import useAppErrorHandler from './hooks/useAppErrorHandler';
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
import ClinicianApp from './pages/ClinicianApp';
import type { PatientSummary } from './types';
import type { InsightsLabItem, InsightsMedicationItem } from './api/generated';

const defaultHighlights = [
  { title: 'LDL Cholesterol', value: '167 mg/dL', trend: 'down', note: 'Jun 2025' },
  { title: 'Omega-3', value: '4.5%', trend: 'down', note: 'Jun 2025' },
  { title: 'Vitamin D', value: '26 ng/mL', trend: 'down', note: 'Jun 2025' },
  { title: 'Hemoglobin A1C', value: '5.4%', trend: 'flat', note: 'Jun 2025' },
];

const a1cSeries = [6.1, 5.9, 5.8, 5.6, 5.5, 5.4];

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

function App() {
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '';
  if (pathname.startsWith('/clinician')) {
    return <ClinicianApp />;
  }

  const patientId = useAppStore((state) => state.patientId);
  const patientSearch = useAppStore((state) => state.patientSearch);
  const accessToken = useAppStore((state) => state.accessToken);
  const currentUser = useAppStore((state) => state.user);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const isClinician = useAppStore((state) => state.isClinician);

  if (isAuthenticated && isClinician) {
    window.location.href = '/clinician';
    return null;
  }
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
  // Document preview is now managed by useDocumentWorkspace hook
  const [insights, setInsights] = useState<{
    lab_total: number;
    lab_abnormal: number;
    recent_labs: InsightsLabItem[];
    active_medications: number;
    recent_medications: InsightsMedicationItem[];
    a1c_series: number[];
  } | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [ocrAvailable, setOcrAvailable] = useState<boolean | null>(null);
  const [latestDocumentStatus, setLatestDocumentStatus] = useState<{
    chunks: { total: number; indexed: number; not_indexed: number };
    processing_status: string;
    processing_error: string | null;
  } | null>(null);
  const [accessRequests, setAccessRequests] = useState<Array<{
    grant_id: number;
    patient_id: number;
    patient_name: string;
    clinician_user_id: number;
    clinician_name: string;
    clinician_email: string;
    status: string;
    scopes: string;
    created_at: string;
  }>>([]);
  const [accessRequestsLoading, setAccessRequestsLoading] = useState(false);
  const [actingGrantId, setActingGrantId] = useState<number | null>(null);
  const { toasts, pushToast } = useToast();
  const { handleError, clearBanner } = useAppErrorHandler({
    setBanner: setErrorBanner,
    pushToast,
  });
  const clearErrorBanner = clearBanner;


  const { patients, isLoading: patientLoading, reload: reloadPatients, hasLoadedSuccessfully } = usePatients({
    search: patientSearch,
    isAuthenticated,
    onError: handleError,
  });
  const {
    records,
    isLoading: recordsLoading,
    reloadRecords,
  } = usePatientRecords({ patientId, onError: handleError, onSuccess: () => setErrorBanner(null) });
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
    api.getHealth()
      .then((health) => {
        console.log('[App] Backend health check passed:', health);
      })
      .catch((error) => {
        console.error('[App] Backend health check failed:', error);
        if (isAuthenticated) {
          setErrorBanner('Warning: Unable to reach backend server. Please ensure the backend is running on port 8000.');
        }
      });
  }, [isAuthenticated]);

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
      .then((headers) => fetch('/api/v1/profile', { headers }))
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
      .then((headers) => fetch(`/api/v1/profile?patient_id=${patientId}`, { headers }))
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

  // Load insights only after patient is verified to exist
  useEffect(() => {
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setInsights(null);
      return;
    }
    
    if (!selectedPatient && currentUser) {
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
  }, [patientId, isAuthenticated, selectedPatient, currentUser, setPatientId, handleError]);

  // Auto-refresh documents while processing (with scroll position preservation)
  useEffect(() => {
    const needsRefresh = documents.some((doc) =>
      ['pending', 'processing'].includes(doc.processing_status),
    );
    if (!needsRefresh) return;
    
    // Preserve scroll position before reload
    let scrollY = window.scrollY;
    let scrollX = window.scrollX;
    
    const interval = setInterval(() => {
      // Save current scroll position
      scrollY = window.scrollY;
      scrollX = window.scrollX;
      
      reloadDocuments();
      
      // Restore scroll position after a brief delay (allowing render to complete)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          window.scrollTo(scrollX, scrollY);
        });
      });
    }, 4000);
    
    return () => clearInterval(interval);
  }, [documents, reloadDocuments]);

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


  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const recordCount = useMemo(() => records.length, [records.length]);
  const showDashboard = isAuthenticated && viewMode === 'dashboard';
  const processedDocs = useMemo(
    () => documents.filter((doc) => doc.is_processed).length,
    [documents],
  );
  const latestDocument = documents[0];

  // Load patient access requests (for clinician approve/deny)
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
    if (isAuthenticated) loadAccessRequests();
  }, [isAuthenticated, loadAccessRequests]);

  const handleApproveAccess = useCallback(async (grantId: number) => {
    setActingGrantId(grantId);
    try {
      await api.patientAccessGrant({ grant_id: grantId });
      pushToast('success', 'Access approved. The clinician can now view this profile.');
      await loadAccessRequests();
    } catch (err) {
      handleError('Failed to approve access', err);
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
    } catch (err) {
      handleError('Failed to deny access', err);
    } finally {
      setActingGrantId(null);
    }
  }, [pushToast, loadAccessRequests, handleError]);

  // Check OCR availability on mount
  useEffect(() => {
    if (isAuthenticated) {
      api.checkOcrAvailability()
        .then((result) => setOcrAvailable(result.available))
        .catch(() => setOcrAvailable(null));
    }
  }, [isAuthenticated]);

  // Check latest document status when it changes
  useEffect(() => {
    if (latestDocument?.id && isAuthenticated) {
      api.getDocumentStatus(latestDocument.id)
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
  }, [latestDocument?.id, isAuthenticated]);
  const latestRecord = records[0];
  const a1cSeriesData = insights?.a1c_series?.length ? insights.a1c_series : a1cSeries;
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

  if (!isAuthenticated) {
    return (
      <div className="app-shell landing">
        <TopBar />
        <ErrorBanner message={errorBanner} />
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
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={errorBanner} />
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
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={errorBanner || 'Unable to load your medical profile. Please refresh the page.'} />
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
      <div className="app-shell">
        <TopBar
          viewMode={viewMode}
          onViewChange={setViewMode}
          patientMeta={selectedPatient}
          selectedPatientId={patientId}
          onPatientChange={setPatientId}
          onDependentAdded={handleDependentAdded}
        />
        <ErrorBanner message={errorBanner} />
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
          <section className="dashboard-main clinician-access-section">
            <div className="insight-panel clinician-access-panel">
              <div className="clinician-access-header">
                <p className="eyebrow">Clinician access</p>
                <h2>Your Patient ID & access requests</h2>
                <p className="subtitle">
                  Share your Patient ID with your clinician so they can request access. Approve or deny requests below.
                </p>
              </div>
              {patientId > 0 && (
                <div className="patient-id-block">
                  <strong>Your Patient ID (share with your clinician):</strong>
                  <span className="patient-id-value">{patientId}</span>
                </div>
              )}
              <div className="access-requests-block">
                <h3>Access requests</h3>
                {accessRequestsLoading ? (
                  <p className="clinician-access-loading">Loading…</p>
                ) : accessRequests.length === 0 ? (
                  <p className="clinician-access-empty">No access requests.</p>
                ) : (
                  <ul className="access-requests-list">
                    {accessRequests.map((req) => (
                      <li key={req.grant_id} className={`access-request-item access-request-${req.status}`}>
                        <div className="access-request-info">
                          <strong>{req.clinician_name}</strong>
                          <span className="access-request-meta">{req.clinician_email}</span>
                          <span className="access-request-meta">
                            For: {req.patient_name} · {req.status}
                          </span>
                        </div>
                        {req.status === 'pending' && (
                          <div className="access-request-actions">
                            <button
                              type="button"
                              className="primary-button compact"
                              disabled={actingGrantId !== null}
                              onClick={() => handleApproveAccess(req.grant_id)}
                            >
                              {actingGrantId === req.grant_id ? 'Approving…' : 'Approve'}
                            </button>
                            <button
                              type="button"
                              className="secondary-button compact"
                              disabled={actingGrantId !== null}
                              onClick={() => handleDenyAccess(req.grant_id)}
                            >
                              Deny
                            </button>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
          <section className="dashboard-main">
            <div className={`insight-panel trends ${!insights?.recent_labs?.length && !documents.length ? 'empty-guidance' : ''}`}>
              <div className="insight-panel-header">
                <div>
                  <p className="eyebrow">Trends</p>
                  <h2>{insights?.recent_labs?.length ? 'A1C over time' : 'Get started'}</h2>
                  <p className="subtitle">{insightsLoading ? 'Loading trends...' : insightSummary}</p>
                </div>
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => setViewMode('chat')}
                >
                  Ask a question
                </button>
              </div>
              {insights?.recent_labs?.length ? (
                <>
                  <svg className="trend-chart" viewBox="0 0 320 90" role="img" aria-label="A1C trend">
                    <path d={buildPath(a1cSeriesData)} />
                  </svg>
                  <div className="trend-list">
                    {insights.recent_labs.map((lab) => (
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
                      <h4>AI extracts the data <span className="ai-badge">MedGemma</span></h4>
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
              )}
            </div>
            <div className="insight-panel focus">
              <h2>Focus areas</h2>
              <div className="focus-row">
                <div>
                  <p className="eyebrow">Latest document</p>
                  <h3>{latestDocument?.title || latestDocument?.original_filename || 'No documents yet'}</h3>
                  <p className="subtitle">
                    {latestDocument
                      ? (() => {
                          const status = latestDocumentStatus;
                          const chunksInfo = status?.chunks;
                          const isReady = status?.processing_status === 'completed' && chunksInfo && chunksInfo.indexed > 0;
                          const hasError = status?.processing_error;
                          const isProcessing = status?.processing_status === 'processing' || status?.processing_status === 'pending';
                          
                          if (hasError) {
                            return `⚠️ ${status.processing_error}`;
                          }
                          if (isProcessing) {
                            return `Processing... · ${latestDocument.page_count || 1} page${latestDocument.page_count === 1 ? '' : 's'}`;
                          }
                          if (chunksInfo && chunksInfo.indexed === 0 && chunksInfo.total > 0) {
                            return `⚠️ ${chunksInfo.total} chunks not indexed · Reprocess needed`;
                          }
                          if (chunksInfo && chunksInfo.indexed > 0) {
                            return `Ready · ${chunksInfo.indexed} indexed chunks · ${latestDocument.page_count || 1} page${latestDocument.page_count === 1 ? '' : 's'}`;
                          }
                          return `Processed · ${latestDocument.page_count || 1} page${latestDocument.page_count === 1 ? '' : 's'}`;
                        })()
                      : 'Upload a report to see document insights.'}
                  </p>
                  {ocrAvailable === false && latestDocument && (
                    <p className="subtitle" style={{ color: '#ff9800', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                      ⚠️ OCR unavailable - scanned/image documents may not extract text
                    </p>
                  )}
                </div>
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => {
                    setViewMode('chat');
                    send(
                      `Summarize the most recent document using only values explicitly shown. Use short, friendly sentences. Do not infer meanings or add follow-ups. If no numeric values are shown, say so in one sentence.`,
                    );
                  }}
                  disabled={!latestDocument || latestDocumentStatus?.processing_status === 'processing' || latestDocumentStatus?.processing_status === 'pending'}
                  title={
                    latestDocument && (latestDocumentStatus?.processing_status === 'processing' || latestDocumentStatus?.processing_status === 'pending')
                      ? 'Document is still processing. Please wait...'
                      : latestDocument && latestDocumentStatus?.processing_status === 'failed'
                      ? 'Document processing failed. Please reprocess the document.'
                      : latestDocument && (latestDocumentStatus?.chunks.indexed ?? 0) === 0 && latestDocumentStatus?.processing_status === 'completed'
                      ? 'Document processed but not yet indexed. Chat may have limited information.'
                      : undefined
                  }
                >
                  Summarize in chat
                </button>
              </div>
              <div className="focus-row">
                <div>
                  <p className="eyebrow">Latest record</p>
                  <h3>{latestRecord?.title || 'No records yet'}</h3>
                  <p className="subtitle">
                    {latestRecord ? formatDate(latestRecord.created_at) : 'Add a clinical note to start tracking.'}
                  </p>
                </div>
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => {
                    setViewMode('chat');
                    const recordName = latestRecord?.title || 'my latest record';
                    send(
                      `Please review the record "${recordName}" and summarize only what is explicitly stated. Do not add recommendations unless they are listed in the record.`,
                    );
                  }}
                  disabled={!latestRecord}
                  title={!latestRecord ? 'No records available. Add a clinical note first to enable this feature.' : undefined}
                >
                  Review in chat
                </button>
              </div>
              <div className="focus-row">
                <div>
                  <p className="eyebrow">Medication focus</p>
                  <h3>
                    {insights?.active_medications
                      ? `${insights.active_medications} active medication${insights.active_medications === 1 ? '' : 's'}`
                      : 'No active medications'}
                  </h3>
                  <p className="subtitle">
                    {insights?.recent_medications?.[0]
                      ? `${insights.recent_medications[0].name} · ${insights.recent_medications[0].dosage || 'dose'}`
                      : 'Add medications to track adherence signals.'}
                  </p>
                </div>
              </div>
            </div>
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
        viewMode={viewMode}
        onViewChange={setViewMode}
        patientMeta={selectedPatient}
        selectedPatientId={patientId}
        onPatientChange={setPatientId}
        onDependentAdded={handleDependentAdded}
      />
      <ErrorBanner message={errorBanner} />
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
