import type { DocumentItem } from '../types';
import type { OcrRefinementResponse } from '../api/generated';

type DocumentsPanelProps = {
  documents: DocumentItem[];
  isLoading: boolean;
  processingIds: number[];
  deletingIds: number[];
  selectedFile: File | null;
  status: string;
  preview?: {
    id: number;
    title: string;
    text: string;
    description?: string | null;
    pageCount?: number | null;
    ocr?: OcrRefinementResponse | null;
  } | null;
  downloadUrl?: string | null;
  isDisabled?: boolean;
  selectedPatient?: { full_name: string; is_dependent?: boolean } | null;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onProcess: (id: number) => void;
  onView: (id: number) => void;
  onDelete: (id: number, label: string) => void;
  onClosePreview: () => void;
};

const DocumentsPanel = ({
  documents,
  isLoading,
  processingIds,
  deletingIds,
  selectedFile,
  status,
  preview,
  downloadUrl,
  isDisabled = false,
  selectedPatient,
  onFileChange,
  onUpload,
  onProcess,
  onView,
  onDelete,
  onClosePreview,
}: DocumentsPanelProps) => {
  const ocrEntities = preview?.ocr?.ocr_entities ?? {};
  const hasOcrEntities = Object.keys(ocrEntities).length > 0;
  const ocrConfidence = preview?.ocr?.ocr_confidence;
  const ocrConfidenceLabel =
    typeof ocrConfidence === 'number' ? `${Math.round(ocrConfidence * 100)}%` : 'n/a';
  const selectedFileLabel = selectedFile ? selectedFile.name : 'No file selected';
  const formatPages = (count?: number | null) => {
    if (!count) return null;
    return `${count} page${count === 1 ? '' : 's'}`;
  };
  const formatStatus = (status: string) => {
    if (status === 'completed') return 'Processed';
    if (status === 'processing') return 'Processing';
    if (status === 'failed') return 'Needs attention';
    return status.charAt(0).toUpperCase() + status.slice(1);
  };
  const getAutoNotes = (description?: string | null) => {
    if (!description) return [];
    return description
      .split('\n')
      .filter((item) => item.startsWith('Auto '));
  };

  return (
    <div className="panel documents">
      <div className="panel-header">
        <h2>Documents</h2>
        <span className="signal-chip">Processed files</span>
      </div>
      <div className="document-list">
        {isDisabled ? (
          <div className="empty-state">Select a patient to view documents.</div>
        ) : isLoading ? (
          <>
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
        </>
      ) : documents.length === 0 ? (
          <div className="empty-state dependent-onboarding">
            {selectedPatient?.is_dependent ? (
              <>
                <span className="empty-state-icon">📄</span>
                <p className="empty-state-title">No records for {selectedPatient.full_name} yet</p>
                <p className="empty-state-subtitle">Upload their medical documents below to start tracking their health.</p>
              </>
            ) : (
              <>
                <span className="empty-state-icon">📄</span>
                <p>No documents yet. Upload a report to get started.</p>
              </>
            )}
          </div>
        ) : (
          documents.map((doc) => (
            <div key={doc.id} className="document-row">
              <div>
                <p>{doc.title || doc.original_filename}</p>
                <small className="document-meta">
                  {formatStatus(doc.processing_status)}
                  {formatPages(doc.page_count) ? ` · ${formatPages(doc.page_count)}` : ''}
                </small>
                {getAutoNotes(doc.description).map((note) => (
                  <div key={note} className="document-note">{note}</div>
                ))}
              </div>
              <div className="document-actions">
                <button
                  className="status-pill"
                  type="button"
                  onClick={() => onProcess(doc.id)}
                  disabled={processingIds.includes(doc.id) || isDisabled}
                >
                  {processingIds.includes(doc.id) ? 'Processing' : 'Process'}
                </button>
                <button
                  className="ghost-button compact"
                  type="button"
                  onClick={() => onView(doc.id)}
                  disabled={!doc.is_processed || isDisabled}
                >
                  View
                </button>
                <button
                  className="delete-btn"
                  type="button"
                  onClick={() => onDelete(doc.id, doc.title || doc.original_filename)}
                  disabled={isDisabled || deletingIds.includes(doc.id)}
                  aria-label={`Delete ${doc.title || doc.original_filename}`}
                  title={`Delete ${doc.title || doc.original_filename}`}
                >
                  {deletingIds.includes(doc.id) ? '⏳' : '🗑️'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
      {preview ? (
        <div className="document-preview">
          <div>
            <h3>{preview.title}</h3>
            <p>{preview.pageCount ? formatPages(preview.pageCount) : 'Extracted text'}</p>
          </div>
          <div className="preview-actions">
            {downloadUrl ? (
              <a className="ghost-button compact" href={downloadUrl} target="_blank" rel="noreferrer">
                Open File
              </a>
            ) : null}
            <button
              className="delete-btn"
              type="button"
              onClick={() => onDelete(preview.id, preview.title)}
              disabled={isDisabled || deletingIds.includes(preview.id)}
              aria-label={`Delete ${preview.title}`}
              title={`Delete ${preview.title}`}
            >
              {deletingIds.includes(preview.id) ? '⏳' : '🗑️'}
            </button>
            <button className="ghost-button compact" type="button" onClick={onClosePreview}>
              Close
            </button>
          </div>
          {getAutoNotes(preview.description).map((note) => (
            <div key={note} className="document-note">{note}</div>
          ))}
          <pre>{preview.text}</pre>
          {preview.ocr?.used_ocr ? (
            <div className="ocr-preview">
              <div className="ocr-header">
                <h4>OCR summary</h4>
                <span>
                  Confidence {ocrConfidenceLabel}
                  {preview.ocr.ocr_language ? ` · ${preview.ocr.ocr_language}` : ''}
                </span>
              </div>
              {preview.ocr.ocr_text_cleaned ? (
                <pre>{preview.ocr.ocr_text_cleaned}</pre>
              ) : null}
              {hasOcrEntities ? (
                <pre>{JSON.stringify(ocrEntities, null, 2)}</pre>
              ) : (
                <p className="ocr-muted">No entities extracted.</p>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="upload-row">
        <input
          type="file"
          id="document-upload"
          name="document"
          onChange={(event) => onFileChange(event.target.files?.[0] || null)}
          aria-label="Upload document"
          disabled={isLoading || isDisabled}
          className="file-input"
        />
        <div className="file-row">
          <label className="ghost-button compact" htmlFor="document-upload">
            Choose file
          </label>
          <span className="file-pill">{selectedFileLabel}</span>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={onUpload}
          disabled={!selectedFile || isLoading || isDisabled}
        >
          Upload Document
        </button>
      </div>
      {status && <p className="status-text">{status}</p>}
    </div>
  );
};

export default DocumentsPanel;
