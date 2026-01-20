import { useCallback, useEffect, useMemo, useState } from 'react';
import './App.css';
import { api, getUserFriendlyMessage } from './api';
import useToast from './hooks/useToast';
import useAppStore from './store/useAppStore';
import usePatients from './hooks/usePatients';
import usePatientRecords from './hooks/usePatientRecords';
import usePatientDocuments from './hooks/usePatientDocuments';
import useChat from './hooks/useChat';
import useMemorySearch from './hooks/useMemorySearch';
import useContextBuilder from './hooks/useContextBuilder';
import useIngestion from './hooks/useIngestion';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';
import ToastStack from './components/ToastStack';
import HeroSection from './components/HeroSection';
import HighlightsPanel from './components/HighlightsPanel';
import ChatPanel from './components/ChatPanel';
import PipelinePanel from './components/PipelinePanel';
import DocumentsPanel from './components/DocumentsPanel';
import MemoryPanel from './components/MemoryPanel';
import ContextPanel from './components/ContextPanel';
import RecordsPanel from './components/RecordsPanel';
import ChatInterface from './components/ChatInterface';
import type { PatientSummary } from './types';

const highlightItems = [
  { title: 'LDL Cholesterol', value: '167 mg/dL', trend: 'down', note: 'Jun 2025' },
  { title: 'Omega-3', value: '4.5%', trend: 'down', note: 'Jun 2025' },
  { title: 'Vitamin D', value: '26 ng/mL', trend: 'down', note: 'Jun 2025' },
  { title: 'Hemoglobin A1C', value: '5.4%', trend: 'flat', note: 'Jun 2025' },
];

const a1cSeries = [6.1, 5.9, 5.8, 5.6, 5.5, 5.4];

const buildPath = (values: number[]) => {
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
  const { toasts, pushToast } = useToast();

  const handleError = useCallback((label: string, error: unknown) => {
    const message = getUserFriendlyMessage(error);
    setErrorBanner(`${label}: ${message}`);
    pushToast('error', `${label}. ${message}`);
  }, [pushToast]);

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
  } = usePatientDocuments({ patientId, onError: handleError, onSuccess: () => setErrorBanner(null) });
  const { messages, question, setQuestion, isStreaming, send } = useChat({
    patientId,
    onError: handleError,
  });
  const { query, setQuery, results, isLoading: searchLoading, search } = useMemorySearch({
    patientId,
    onError: handleError,
    onInfo: (message) => pushToast('info', message),
  });
  const { question: contextQuestion, setQuestion: setContextQuestion, result, isLoading: contextLoading, generate } =
    useContextBuilder({
      patientId,
      onError: handleError,
      onSuccess: (message) => pushToast('success', message),
    });
  const { payload, setPayload, status, isLoading: ingestionLoading, ingest } = useIngestion({
    onError: handleError,
    onSuccess: (message) => pushToast('success', message),
  });

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
        setAccessToken(null);
        handleError('Session expired', error);
      });
  }, [accessToken, currentUser, setAccessToken, setUser, handleError]);

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
      handleError('Failed to upload document', error);
      setDocumentStatus('Upload failed.');
    }
  };

  const handleChatUpload = async (file: File) => {
    if (!patientId) {
      pushToast('info', 'Select a patient before uploading a report.');
      return;
    }
    setIsChatUploading(true);
    setChatUploadStatus('Uploading report...');
    try {
      const uploaded = await api.uploadDocument(patientId, file, { title: file.name });
      setChatUploadStatus('Processing for chat...');
      await api.processDocument(uploaded.id);
      setChatUploadStatus('Ready to chat with this report.');
      pushToast('success', 'Report uploaded and processed.');
      await reloadDocuments();
    } catch (error) {
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
  const selectedPatient = autoSelectedPatient || patients.find((patient) => patient.id === patientId);

  // Show landing page if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="app-shell">
        <TopBar />
        <ErrorBanner message={errorBanner} />
        <main className="dashboard">
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
          <section className="grid locked" aria-hidden={true}>
            <HighlightsPanel items={highlightItems} chartPath={buildPath(a1cSeries)} isLoading={recordsLoading} />
            <ChatPanel
              messages={messages}
              question={question}
              isStreaming={isStreaming}
              isDisabled={true}
              uploadStatus={chatUploadStatus}
              isUploading={isChatUploading}
              onQuestionChange={setQuestion}
              onSend={send}
              onUploadFile={handleChatUpload}
            />
            <PipelinePanel
              payload={payload}
              status={status}
              isLoading={ingestionLoading}
              isDisabled={true}
              onPayloadChange={setPayload}
              onIngest={ingest}
            />
            <DocumentsPanel
              documents={documents}
              isLoading={documentsLoading}
              processingIds={processingDocs}
              selectedFile={selectedFile}
              status={documentStatus}
              isDisabled={true}
              onFileChange={setSelectedFile}
              onUpload={handleUploadDocument}
              onProcess={handleProcessDocument}
            />
            <MemoryPanel
              query={query}
              isLoading={searchLoading}
              results={results}
              isDisabled={true}
              onQueryChange={setQuery}
              onSearch={search}
            />
            <ContextPanel
              question={contextQuestion}
              result={result}
              isLoading={contextLoading}
              isDisabled={true}
              onQuestionChange={setContextQuestion}
              onGenerate={generate}
            />
            <RecordsPanel
              records={records}
              isLoading={recordsLoading}
              recordCount={recordCount}
              formData={formData}
              isSubmitting={isSubmitting}
              isDisabled={true}
              onFormChange={(field, value) => setFormData((prev) => ({ ...prev, [field]: value }))}
              onSubmit={handleSubmit}
              formatDate={formatDate}
            />
          </section>
        </main>
        <ToastStack toasts={toasts} />
      </div>
    );
  }

  // Show full-screen chat interface when authenticated
  // Show loading state while patient is being created/selected
  // Only show loading if we're actively loading and haven't failed
  const isLoadingPatient = !selectedPatient && isAuthenticated && currentUser && !patientLoadingFailed;
  
  if (isLoadingPatient) {
    return (
      <div className="app-shell chat-mode">
        <TopBar />
        <ErrorBanner message={errorBanner} />
        <div className="chat-loading-state">
          <div className="loading-spinner" />
          <p>Setting up your medical profile...</p>
          <p className="loading-hint">This may take a few moments...</p>
        </div>
        <ToastStack toasts={toasts} />
      </div>
    );
  }
  
  // If there's an error loading patient, show chat interface with error message
  // This prevents the user from being stuck on the loading screen
  if (!selectedPatient && isAuthenticated && currentUser && patientLoadingFailed) {
    return (
      <div className="app-shell chat-mode">
        <TopBar />
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
      </div>
    );
  }

  return (
    <div className="app-shell chat-mode">
      <TopBar />
      <ErrorBanner message={errorBanner} />
      <ChatInterface
        messages={messages}
        question={question}
        isStreaming={isStreaming}
        isDisabled={!selectedPatient}
        selectedPatient={selectedPatient}
        showHeader={false}
        onQuestionChange={setQuestion}
        onSend={send}
        onUploadFile={handleChatUpload}
      />
      <ToastStack toasts={toasts} />
    </div>
  );
}

export default App;
