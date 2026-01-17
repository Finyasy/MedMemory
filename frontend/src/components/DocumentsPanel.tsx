import type { DocumentItem } from '../types';

type DocumentsPanelProps = {
  documents: DocumentItem[];
  isLoading: boolean;
  processingIds: number[];
  selectedFile: File | null;
  status: string;
  isDisabled?: boolean;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onProcess: (id: number) => void;
};

const DocumentsPanel = ({
  documents,
  isLoading,
  processingIds,
  selectedFile,
  status,
  isDisabled = false,
  onFileChange,
  onUpload,
  onProcess,
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
              <button
                className="status-pill"
                type="button"
                onClick={() => onProcess(doc.id)}
                disabled={processingIds.includes(doc.id) || isDisabled}
              >
                {processingIds.includes(doc.id) ? 'Processing' : 'Process'}
              </button>
            </div>
          ))
        )}
      </div>
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
