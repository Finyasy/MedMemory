import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api';
import useChat from '../hooks/useChat';
import useAppErrorHandler from '../hooks/useAppErrorHandler';
import useToast from '../hooks/useToast';
import ChatInterface from '../components/ChatInterface';
import type { DocumentItem, MedicalRecord } from '../types';

type ClinicianPatientViewProps = {
  patientId: number;
  patientName: string;
  onBack: () => void;
};

export default function ClinicianPatientView({ patientId, patientName, onBack }: ClinicianPatientViewProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingRecords, setLoadingRecords] = useState(true);
  const { pushToast } = useToast();
  const { handleError } = useAppErrorHandler({
    setBanner: () => {},
    pushToast,
  });

  const load = useCallback(async () => {
    setLoadingDocs(true);
    setLoadingRecords(true);
    try {
      const [docs, recs] = await Promise.all([
        api.listClinicianPatientDocuments(patientId),
        api.listClinicianPatientRecords(patientId),
      ]);
      setDocuments(docs);
      setRecords(recs);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        onBack();
        return;
      }
      handleError('Failed to load patient data', err);
    } finally {
      setLoadingDocs(false);
      setLoadingRecords(false);
    }
  }, [patientId, onBack, handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const {
    messages,
    question,
    setQuestion,
    isStreaming,
    send,
  } = useChat({
    patientId,
    onError: handleError,
    clinicianMode: true,
  });

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  return (
    <div className="clinician-patient-view">
      <header className="clinician-header">
        <div className="clinician-header-inner">
          <button type="button" className="ghost-button" onClick={onBack}>
            ← Back to dashboard
          </button>
          <h1>{patientName}</h1>
        </div>
      </header>
      <main className="clinician-patient-main">
        <section className="clinician-patient-section">
          <h2>Documents</h2>
          {loadingDocs ? (
            <p className="clinician-loading">Loading…</p>
          ) : documents.length === 0 ? (
            <p className="clinician-empty">No documents.</p>
          ) : (
            <ul className="clinician-doc-list">
              {documents.map((d) => (
                <li key={d.id}>
                  <strong>{d.title || d.original_filename}</strong>
                  <span className="clinician-meta">{d.processing_status}</span>
                  <span className="clinician-meta">
                    {formatDate((d as { received_date?: string; created_at?: string }).received_date ?? (d as { created_at?: string }).created_at ?? '')}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="clinician-patient-section">
          <h2>Records</h2>
          {loadingRecords ? (
            <p className="clinician-loading">Loading…</p>
          ) : records.length === 0 ? (
            <p className="clinician-empty">No records.</p>
          ) : (
            <ul className="clinician-record-list">
              {records.map((r) => (
                <li key={r.id}>
                  <strong>{r.title}</strong>
                  <span className="clinician-meta">{formatDate(r.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="clinician-chat-section">
          <h2>Technical chat</h2>
          <p className="clinician-chat-hint">Uses clinician mode: terse, cited, “Not in documents” when missing.</p>
          <ChatInterface
            messages={messages}
            question={question}
            isStreaming={isStreaming}
            isDisabled={false}
            selectedPatient={{ id: patientId, full_name: patientName }}
            showHeader={false}
            onQuestionChange={setQuestion}
            onSend={send}
          />
        </section>
      </main>
    </div>
  );
}
