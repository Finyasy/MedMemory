import { useCallback, useEffect, useMemo, useState } from 'react';
import './App.css';
import { ApiError, api, getUserFriendlyMessage } from './api';
import useToast from './hooks/useToast';
import useAppStore from './store/useAppStore';
import usePatients from './hooks/usePatients';
import usePatientRecords from './hooks/usePatientRecords';
import usePatientDocuments from './hooks/usePatientDocuments';
import useChat from './hooks/useChat';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';
import ToastStack from './components/ToastStack';
import HeroSection from './components/HeroSection';
import DocumentsPanel from './components/DocumentsPanel';
import RecordsPanel from './components/RecordsPanel';
import ChatInterface from './components/ChatInterface';
import LocalizationModal from './components/LocalizationModal';
import type { DocumentOcrRefinement, LocalizationBox, PatientSummary } from './types';
import { getChatUploadKind, isCxrFilename } from './utils/uploadRouting';

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

const getExistingDocumentId = (error: unknown) => {
  let message = '';
  if (error instanceof ApiError) {
    message = error.message;
  } else if (error && typeof error === 'object' && 'body' in error) {
    const body = (error as { body?: { detail?: string; error?: { message?: string } }; message?: string }).body;
    message = body?.detail || body?.error?.message || (error as { message?: string }).message || '';
  } else if (error instanceof Error) {
    message = error.message;
  }
  const match = /Document already exists with ID (\d+)/.exec(message);
  return match ? Number(match[1]) : null;
};

function App() {
  const patientId = useAppStore((state) => state.patientId);
  const patientSearch = useAppStore((state) => state.patientSearch);
  const accessToken = useAppStore((state) => state.accessToken);
  const currentUser = useAppStore((state) => state.user);
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const setAccessToken = useAppStore((state) => state.setAccessToken);
  const setUser = useAppStore((state) => state.setUser);
  const setPatientId = useAppStore((state) => state.setPatientId);
  const setPatientSearch = useAppStore((state) => state.setPatientSearch);
  const [processingDocs, setProcessingDocs] = useState<number[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentStatus, setDocumentStatus] = useState('');
  const [chatUploadStatus, setChatUploadStatus] = useState('');
  const [isChatUploading, setIsChatUploading] = useState(false);
  const [formData, setFormData] = useState({ title: '', content: '', record_type: 'general' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [patientLoadingFailed, setPatientLoadingFailed] = useState(false);
  const [autoSelectedPatient, setAutoSelectedPatient] = useState<PatientSummary | null>(null);
  const [viewMode, setViewMode] = useState<'chat' | 'dashboard'>('chat');
  const [documentPreview, setDocumentPreview] = useState<{
    id: number;
    title: string;
    text: string;
    description?: string | null;
    pageCount?: number | null;
    ocr?: DocumentOcrRefinement | null;
  } | null>(null);
  const [localizationPreview, setLocalizationPreview] = useState<{
    imageUrl: string;
    boxes: LocalizationBox[];
  } | null>(null);
  const [documentDownloadUrl, setDocumentDownloadUrl] = useState<string | null>(null);
  const [insights, setInsights] = useState<{
    lab_total: number;
    lab_abnormal: number;
    recent_labs: Array<{
      test_name: string;
      value?: string | null;
      unit?: string | null;
      collected_at?: string | null;
      is_abnormal: boolean;
    }>;
    active_medications: number;
    recent_medications: Array<{
      name: string;
      dosage?: string | null;
      frequency?: string | null;
      status?: string | null;
      prescribed_at?: string | null;
      start_date?: string | null;
    }>;
    a1c_series: number[];
  } | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const { toasts, pushToast } = useToast();

  const handleError = useCallback((label: string, error: unknown) => {
    const message = getUserFriendlyMessage(error);
    setErrorBanner(`${label}: ${message}`);
    pushToast('error', `${label}. ${message}`);
  }, [pushToast]);
  const clearErrorBanner = useCallback(() => {
    setErrorBanner(null);
  }, []);

  const { patients, isLoading: patientLoading } = usePatients({
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
  

  // Compute selectedPatient early so it can be used in useEffect hooks
  const selectedPatient = useMemo(
    () => autoSelectedPatient || patients.find((patient) => patient.id === patientId),
    [autoSelectedPatient, patients, patientId]
  );

  useEffect(() => {
    // Test if backend is accessible through proxy
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

  // Fetch user info if we have a token but no user
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

  // Verify patient exists if patientId is set but selectedPatient is not available
  // Only run this after patients have been loaded (not loading and not empty due to no patients)
  useEffect(() => {
    if (!currentUser || !accessToken || !patientId || patientId <= 0) {
      return;
    }
    
    // Only verify if patients have been loaded (not currently loading)
    // If we have a patientId but no selectedPatient, and patients list is available, verify it exists
    if (!selectedPatient && !patientLoading && patients.length >= 0) {
      const patientExists = patients.some((p) => p.id === patientId);
      if (!patientExists && patients.length > 0) {
        // Patient list is loaded and patient doesn't exist - clear it
        console.warn('Patient ID does not exist in patient list, clearing it');
        setPatientId(0);
      }
    }
  }, [currentUser, accessToken, patientId, selectedPatient, patients, patientLoading, setPatientId]);

  // Auto-select or create patient when user is set and no patient is selected
  useEffect(() => {
    if (!currentUser || !accessToken || patientId > 0) {
      setPatientLoadingFailed(false);
      return;
    }
    
    let cancelled = false;
    setPatientLoadingFailed(false);
    
    // Add a timeout to prevent infinite loading
    const maxWaitTimeout = setTimeout(() => {
      if (cancelled || patientId > 0) return;
      console.error('Patient loading timeout - taking too long');
      setPatientLoadingFailed(true);
      handleError('Loading timeout', new Error('Patient profile loading is taking too long. Please refresh the page or check your connection.'));
    }, 15000); // 15 second timeout
    
    // Small delay to ensure token is fully persisted
    const timeoutId = setTimeout(() => {
      if (cancelled) return;
      
      // Verify token is still available
      const token = window.localStorage.getItem('medmemory_access_token');
      if (!token) {
        console.error('Access token not found in localStorage');
        setPatientLoadingFailed(true);
        handleError('Authentication error', new Error('Access token missing'));
        clearTimeout(maxWaitTimeout);
        return;
      }
      
      console.log('Loading patient profile...');
      
      // Auto-select or create patient for the logged-in user
      api
        .listPatients()
        .then((patientList) => {
          if (cancelled) return;
          clearTimeout(maxWaitTimeout);
          console.log('Patient list loaded:', patientList);
          
          if (patientList.length > 0) {
            // Auto-select the first patient
            console.log('Selecting patient:', patientList[0].id);
            setPatientId(patientList[0].id);
            setAutoSelectedPatient(patientList[0]);
            setPatientLoadingFailed(false);
          } else {
            // Auto-create a patient from user info
            console.log('No patients found, creating new patient profile...');
            const nameParts = currentUser.full_name.split(' ');
            const firstName = nameParts[0] || currentUser.email.split('@')[0];
            const lastName = nameParts.slice(1).join(' ') || 'User';
            api
              .createPatient({
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
          // More detailed error logging
          console.error('Failed to load patient profile:', error);
          if (error instanceof Error) {
            console.error('Error details:', error.message, error.stack);
          }
          setPatientLoadingFailed(true);
          // Always show error to user so they know something went wrong
          handleError('Failed to load patient profile', error);
        });
    }, 100); // Small delay to ensure state is settled
    
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

  useEffect(() => {
    setDocumentPreview(null);
    setDocumentDownloadUrl(null);
  }, [patientId]);

  useEffect(() => {
    if (!patientId || selectedPatient || !isAuthenticated) return;
    api
      .getPatient(patientId)
      .then((patient) => {
        setAutoSelectedPatient(patient);
      })
      .catch(() => {
        // Let other flows handle errors; avoid blocking login UX.
      });
  }, [patientId, selectedPatient, isAuthenticated]);

  useEffect(() => {
    // Only load insights if we have a valid patient selected and authenticated
    // Wait for selectedPatient to be available to ensure patient exists
    if (!patientId || patientId <= 0 || !isAuthenticated) {
      setInsights(null);
      return;
    }
    
    // If we have a patientId but no selectedPatient, verify the patient exists first
    // This handles the case where patientId might be stale or invalid
    if (!selectedPatient && currentUser) {
      // Patient verification is in progress, don't load insights yet
      setInsights(null);
      return;
    }
    
    setInsightsLoading(true);
    api
      .getPatientInsights(patientId)
      .then((data) => {
        setInsights(data);
      })
      .catch((error) => {
        // If patient not found (404), clear patientId and let auto-select handle it
        if (error instanceof ApiError && error.status === 404) {
          console.warn('Patient not found for insights, clearing patientId');
          setPatientId(0);
          setInsights(null);
        } else {
          // Only show error for non-404 errors (network, server errors, etc.)
          // Don't show error for 404s as they're handled gracefully
          handleError('Failed to load insights', error);
        }
      })
      .finally(() => setInsightsLoading(false));
  }, [patientId, isAuthenticated, selectedPatient, currentUser, setPatientId, handleError]);

  useEffect(() => {
    const needsRefresh = documents.some((doc) =>
      ['pending', 'processing'].includes(doc.processing_status),
    );
    if (!needsRefresh) return;
    const interval = setInterval(() => {
      reloadDocuments();
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

  const handleUploadDocument = async () => {
    if (!selectedFile) return;
    setDocumentStatus('Uploading document...');
    try {
      await api.uploadDocument(patientId, selectedFile, { title: selectedFile.name });
      setSelectedFile(null);
      setDocumentStatus('Upload complete.');
      pushToast('success', 'Document uploaded.');
      await reloadDocuments();
    } catch (error) {
      const existingId = getExistingDocumentId(error);
      if (existingId) {
        setSelectedFile(null);
        setDocumentStatus('Already uploaded. Using existing document.');
        pushToast('info', `Document already exists (ID ${existingId}). Using existing file.`);
        await reloadDocuments();
        return;
      }
      handleError('Failed to upload document', error);
      setDocumentStatus('Upload failed.');
    }
  };

  const handleChatUpload = async (file: File | File[]) => {
    const files = Array.isArray(file) ? file : [file];
    for (const single of files) {
      await handleSingleChatUpload(single);
    }
  };

  const handleLocalizeUpload = async (file: File) => {
    if (!patientId) {
      pushToast('info', 'Select a patient before localizing.');
      return;
    }
    setIsChatUploading(true);
    setChatUploadStatus('Localizing findings...');
    const imageUrl = URL.createObjectURL(file);
    try {
      const modality = isCxrFilename(file.name) ? 'cxr' : 'imaging';
      const prompt = question.trim() || 'Localize findings in this image.';
      pushMessage({ role: 'user', content: `${prompt}\n[Localization: ${file.name}]` });
      const response = await api.localizeFindings(patientId, prompt, file, modality);
      setLocalizationPreview({ imageUrl, boxes: response.boxes });
      const topLabels = response.boxes
        .slice(0, 3)
        .map((box) => `${box.label} (${Math.round(box.confidence * 100)}%)`)
        .join(', ');
      const summaryText = response.boxes.length
        ? `Localization found ${response.boxes.length} region(s): ${topLabels}.`
        : 'Localization found no regions.';
      pushMessage({ role: 'assistant', content: summaryText });
      try {
        await api.uploadDocument(patientId, file, {
          title: file.name,
          document_type: 'imaging',
          category: 'localization',
          description: `Auto localization: ${summaryText}`,
        });
      } catch {
        // Optional persistence; ignore failures.
      }
      setChatUploadStatus('Localization complete.');
      pushToast('success', 'Localization ready.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        pushToast('error', 'Localization endpoint unavailable. Restart the backend.');
      } else {
        handleError('Failed to localize image', error);
      }
      setChatUploadStatus('Localization failed.');
      URL.revokeObjectURL(imageUrl);
    } finally {
      setIsChatUploading(false);
    }
  };

  const handleSingleChatUpload = async (single: File) => {
    const uploadKind = getChatUploadKind(single);
    if (!patientId) {
      pushToast('info', 'Select a patient before uploading a report.');
      return;
    }
    if (uploadKind === 'dicom') {
      pushToast('info', 'Please upload DICOM series as a .zip file.');
      return;
    }
    if (uploadKind === 'wsi') {
      setIsChatUploading(true);
      setChatUploadStatus('Analyzing WSI patches...');
      try {
        await sendWsi(single, question);
        setChatUploadStatus('WSI analysis complete.');
      } catch (error) {
        setChatUploadStatus('WSI analysis failed.');
      } finally {
        setIsChatUploading(false);
      }
      return;
    }
    if (uploadKind === 'volume') {
      setIsChatUploading(true);
      setChatUploadStatus('Analyzing volume...');
      try {
        await sendVolume(single, question);
        setChatUploadStatus('Volume analysis complete.');
      } catch (error) {
        setChatUploadStatus('Volume analysis failed.');
      } finally {
        setIsChatUploading(false);
      }
      return;
    }
    if (uploadKind === 'image') {
      if (isCxrFilename(single.name)) {
        setIsChatUploading(true);
        setChatUploadStatus('Uploading chest X-ray...');
        try {
          const uploaded = await api.uploadDocument(patientId, single, { title: single.name });
          setChatUploadStatus('Generating CXR comparison...');
          await api.processDocument(uploaded.id);
          setChatUploadStatus('CXR uploaded with comparison.');
          pushToast('success', 'Chest X-ray uploaded. Comparison added to document.');
          await reloadDocuments();
        } catch (error) {
          handleError('Failed to upload chest X-ray', error);
          setChatUploadStatus('Upload failed.');
        } finally {
          setIsChatUploading(false);
        }
        return;
      }
      setIsChatUploading(true);
      setChatUploadStatus('Analyzing image...');
      try {
        await sendVision(single, question);
        setChatUploadStatus('Image analysis complete.');
        pushToast('success', 'Image analyzed with MedGemma.');
      } catch (error) {
        handleError('Failed to analyze image', error);
        setChatUploadStatus('Image analysis failed.');
      } finally {
        setIsChatUploading(false);
      }
      return;
    }
    setIsChatUploading(true);
    setChatUploadStatus('Uploading report...');
    try {
      const uploaded = await api.uploadDocument(patientId, single, { title: single.name });
      setChatUploadStatus('Processing for chat...');
      await api.processDocument(uploaded.id);
      setChatUploadStatus('Ready to chat with this report.');
      pushToast('success', 'Report uploaded and processed.');
      await reloadDocuments();
    } catch (error) {
      const existingId = getExistingDocumentId(error);
      if (existingId) {
        try {
          setChatUploadStatus('Processing existing report...');
          await api.processDocument(existingId);
          setChatUploadStatus('Ready to chat with this report.');
          pushToast('info', `Report already exists (ID ${existingId}). Using existing document.`);
          await reloadDocuments();
          return;
        } catch (processError) {
          handleError('Failed to process existing report', processError);
          setChatUploadStatus('Processing failed.');
          return;
        }
      }
      handleError('Failed to upload chat file', error);
      setChatUploadStatus('Upload failed.');
    } finally {
      setIsChatUploading(false);
    }
  };

  const handleProcessDocument = async (documentId: number) => {
    setProcessingDocs((prev) => [...prev, documentId]);
    setDocumentStatus('Processing document...');
    try {
      await api.processDocument(documentId);
      setDocumentStatus('Processing complete.');
      pushToast('success', 'Document processed.');
      await reloadDocuments();
    } catch (error) {
      handleError('Failed to process document', error);
      setDocumentStatus('Processing failed.');
    } finally {
      setProcessingDocs((prev) => prev.filter((id) => id !== documentId));
    }
  };

  const handleViewDocument = async (documentId: number) => {
    const doc = documents.find((item) => item.id === documentId);
    if (!doc) return;
    if (!doc.is_processed) {
      pushToast('info', 'Process the document to view extracted text.');
      return;
    }
    try {
      const [textResponse, ocrResponse] = await Promise.all([
        api.getDocumentText(documentId),
        api.getDocumentOcr(documentId).catch(() => null),
      ]);
      setDocumentPreview({
        id: documentId,
        title: doc.title || doc.original_filename,
        text: textResponse.extracted_text,
        description: doc.description,
        pageCount: textResponse.page_count,
        ocr: ocrResponse,
      });
      setDocumentDownloadUrl(`${window.location.origin}/api/v1/documents/${documentId}/download`);
      pushToast('success', 'Document loaded.');
    } catch (error) {
      handleError('Failed to load document text', error);
    }
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
  const latestRecord = records[0];
  const a1cSeriesData = insights?.a1c_series?.length ? insights.a1c_series : a1cSeries;
  const highlightItems = useMemo(() => {
    if (!insights?.recent_labs?.length) return defaultHighlights;
    return insights.recent_labs.map((lab) => ({
      title: lab.test_name,
      value: `${lab.value || '—'} ${lab.unit || ''}`.trim(),
      trend: lab.is_abnormal ? 'down' : 'flat',
      note: lab.collected_at ? formatDate(lab.collected_at) : 'Latest',
    }));
  }, [insights, formatDate]);

  const localizationModal = localizationPreview ? (
    <LocalizationModal
      imageUrl={localizationPreview.imageUrl}
      boxes={localizationPreview.boxes}
      onClose={() => {
        URL.revokeObjectURL(localizationPreview.imageUrl);
        setLocalizationPreview(null);
      }}
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

  // Show landing page if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="app-shell landing">
        <TopBar />
        <ErrorBanner message={errorBanner} />
        <main className="landing-main">
          <HeroSection
            selectedPatient={selectedPatient}
            isLoading={patientLoading}
            patients={patients}
            searchValue={patientSearch}
            isSearchLoading={patientLoading}
            selectedPatientId={patientId}
            onSearchChange={setPatientSearch}
            onSelectPatient={setPatientId}
            isAuthenticated={isAuthenticated}
          />
        </main>
        <ToastStack toasts={toasts} />
        {localizationModal}
      </div>
    );
  }

  // Show full-screen chat interface when authenticated
  // Show loading state while patient is being created/selected
  // Only show loading if we're actively loading and haven't failed
  const isLoadingPatient = patientId === 0 && isAuthenticated && currentUser && !patientLoadingFailed;
  
  if (isLoadingPatient) {
    return (
      <div className="app-shell chat-mode">
        <TopBar viewMode={viewMode} onViewChange={setViewMode} patientMeta={selectedPatient} />
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
  
  // If there's an error loading patient, show chat interface with error message
  // This prevents the user from being stuck on the loading screen
  if (!selectedPatient && isAuthenticated && currentUser && patientLoadingFailed) {
    return (
      <div className="app-shell chat-mode">
        <TopBar viewMode={viewMode} onViewChange={setViewMode} patientMeta={selectedPatient} />
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
        <TopBar viewMode={viewMode} onViewChange={setViewMode} patientMeta={selectedPatient} />
        <ErrorBanner message={errorBanner} />
        <main className="dashboard">
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
                      ? `Processed · ${latestDocument.page_count || 1} page${latestDocument.page_count === 1 ? '' : 's'}`
                      : 'Upload a report to see document insights.'}
                  </p>
                </div>
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => setViewMode('chat')}
                  disabled={!latestDocument}
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
                  onClick={() => setViewMode('chat')}
                  disabled={!latestRecord}
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
              processingIds={processingDocs}
              selectedFile={selectedFile}
              status={documentStatus}
              preview={documentPreview}
              downloadUrl={documentDownloadUrl}
              isDisabled={!selectedPatient}
              onFileChange={setSelectedFile}
              onUpload={handleUploadDocument}
              onProcess={handleProcessDocument}
              onView={handleViewDocument}
              onClosePreview={() => {
                setDocumentPreview(null);
                setDocumentDownloadUrl(null);
              }}
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
      <TopBar viewMode={viewMode} onViewChange={setViewMode} patientMeta={selectedPatient} />
      <ErrorBanner message={errorBanner} />
      <ChatInterface
        messages={messages}
        question={question}
        isStreaming={isStreaming}
        isDisabled={!patientId}
        selectedPatient={selectedPatient}
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
