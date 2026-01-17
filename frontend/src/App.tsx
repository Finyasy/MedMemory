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
  const [formData, setFormData] = useState({ title: '', content: '', record_type: 'general' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const { toasts, pushToast } = useToast();

  const handleError = useCallback((label: string, error: unknown) => {
    const message = getUserFriendlyMessage(error);
    setErrorBanner(`${label}: ${message}`);
    pushToast('error', `${label}. ${message}`);
  }, [pushToast]);

  const { patients, isLoading: patientLoading } = usePatients({
    search: patientSearch,
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
    api.getHealth().catch(() => {
      // Health check failed, handled by error banner
    });
  }, []);

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
      .then((user) => setUser(user))
      .catch((error) => {
        setAccessToken(null);
        handleError('Session expired', error);
      });
  }, [accessToken, currentUser, setAccessToken, setUser, handleError]);

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
  const selectedPatient = patients.find((patient) => patient.id === patientId);
  const isPatientSelected = Boolean(selectedPatient);
  const isPanelDisabled = !isAuthenticated || !isPatientSelected;

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

        {!isAuthenticated && (
          <div className="auth-gate" role="status">
            Sign in to access patient memory, ingestion, and chat tools.
          </div>
        )}
        <section className={`grid${isAuthenticated ? '' : ' locked'}`} aria-hidden={!isAuthenticated}>
          <HighlightsPanel items={highlightItems} chartPath={buildPath(a1cSeries)} isLoading={recordsLoading} />
          <ChatPanel
            messages={messages}
            question={question}
            isStreaming={isStreaming}
            isDisabled={isPanelDisabled}
            onQuestionChange={setQuestion}
            onSend={send}
          />
          <PipelinePanel
            payload={payload}
            status={status}
            isLoading={ingestionLoading}
            isDisabled={isPanelDisabled}
            onPayloadChange={setPayload}
            onIngest={ingest}
          />
          <DocumentsPanel
            documents={documents}
            isLoading={documentsLoading}
            processingIds={processingDocs}
            selectedFile={selectedFile}
            status={documentStatus}
            isDisabled={isPanelDisabled}
            onFileChange={setSelectedFile}
            onUpload={handleUploadDocument}
            onProcess={handleProcessDocument}
          />
          <MemoryPanel
            query={query}
            isLoading={searchLoading}
            results={results}
            isDisabled={isPanelDisabled}
            onQueryChange={setQuery}
            onSearch={search}
          />
          <ContextPanel
            question={contextQuestion}
            result={result}
            isLoading={contextLoading}
            isDisabled={isPanelDisabled}
            onQuestionChange={setContextQuestion}
            onGenerate={generate}
          />
          <RecordsPanel
            records={records}
            isLoading={recordsLoading}
            recordCount={recordCount}
            formData={formData}
            isSubmitting={isSubmitting}
            isDisabled={isPanelDisabled}
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

export default App;
