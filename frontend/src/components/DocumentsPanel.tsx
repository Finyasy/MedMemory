import type { DocumentItem } from '../types';

type DocumentsPanelProps = {
  documents: DocumentItem[];
  isLoading: boolean;
  processingIds: number[];
  selectedFile: File | null;
  status: string;
  preview?: {
    id: number;
    title: string;
    text: string;
    pageCount?: number | null;
  } | null;
  downloadUrl?: string | null;
  isDisabled?: boolean;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onProcess: (id: number) => void;
  onView: (id: number) => void;
  onClosePreview: () => void;
};

const DocumentsPanel = ({
  documents,
  isLoading,
  processingIds,
  selectedFile,
  status,
  preview,
  downloadUrl,
  isDisabled = false,
  onFileChange,
  onUpload,
  onProcess,
  onView,
  onClosePreview,
}: DocumentsPanelProps) => {
  return (
    <div className="panel documents">
      <div className="panel-header">
        <h2>Documents</h2>
        <span className="signal-chip">OCR + Chunking</span>
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
          <div className="empty-state">No documents for this patient.</div>
        ) : (
          documents.map((doc) => (
            <div key={doc.id} className="document-row">
              <div>
                <p>{doc.title || doc.original_filename}</p>
                <small>
                  {doc.processing_status} · {doc.page_count || 0} pages
                </small>
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
              </div>
            </div>
          ))
        )}
      </div>
      {preview ? (
        <div className="document-preview">
          <div>
            <h3>{preview.title}</h3>
            <p>{preview.pageCount ? `${preview.pageCount} pages` : 'Extracted text'}</p>
          </div>
          <div className="preview-actions">
            {downloadUrl ? (
              <a className="ghost-button compact" href={downloadUrl} target="_blank" rel="noreferrer">
                Open File
              </a>
            ) : null}
            <button className="ghost-button compact" type="button" onClick={onClosePreview}>
              Close
            </button>
          </div>
          <pre>{preview.text}</pre>
        </div>
      ) : null}
      <div className="upload-row">
        <input
          type="file"
          onChange={(event) => onFileChange(event.target.files?.[0] || null)}
          aria-label="Upload document"
          disabled={isLoading || isDisabled}
        />
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
