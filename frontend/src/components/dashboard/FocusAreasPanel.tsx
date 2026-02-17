import type { DocumentItem, MedicalRecord } from '../../types';

type LatestDocumentStatus = {
  chunks: { total: number; indexed: number; not_indexed: number };
  processing_status: string;
  processing_error: string | null;
};

type FocusAreasPanelProps = {
  latestDocument: DocumentItem | undefined;
  latestDocumentStatus: LatestDocumentStatus | null;
  latestRecord: MedicalRecord | undefined;
  ocrAvailable: boolean | null;
  activeMedications: number;
  recentMedicationSummary: string;
  onSummarizeLatestDocument: () => void;
  onReviewLatestRecord: () => void;
  formatDate: (date: string) => string;
};

function FocusAreasPanel({
  latestDocument,
  latestDocumentStatus,
  latestRecord,
  ocrAvailable,
  activeMedications,
  recentMedicationSummary,
  onSummarizeLatestDocument,
  onReviewLatestRecord,
  formatDate,
}: FocusAreasPanelProps) {
  const latestDocumentSubtitle = latestDocument
    ? (() => {
        const status = latestDocumentStatus;
        const chunksInfo = status?.chunks;
        const hasError = status?.processing_error;
        const isProcessing =
          status?.processing_status === 'processing' || status?.processing_status === 'pending';

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
    : 'Upload a report to see document insights.';

  const summarizeDisabled =
    !latestDocument ||
    latestDocumentStatus?.processing_status === 'processing' ||
    latestDocumentStatus?.processing_status === 'pending';

  const summarizeTitle =
    latestDocument &&
    (latestDocumentStatus?.processing_status === 'processing' ||
      latestDocumentStatus?.processing_status === 'pending')
      ? 'Document is still processing. Please wait...'
      : latestDocument && latestDocumentStatus?.processing_status === 'failed'
        ? 'Document processing failed. Please reprocess the document.'
        : latestDocument &&
            (latestDocumentStatus?.chunks.indexed ?? 0) === 0 &&
            latestDocumentStatus?.processing_status === 'completed'
          ? 'Document processed but not yet indexed. Chat may have limited information.'
          : undefined;

  return (
    <div className="insight-panel focus">
      <h2>Focus areas</h2>
      <div className="focus-row">
        <div>
          <p className="eyebrow">Latest document</p>
          <h3>{latestDocument?.title || latestDocument?.original_filename || 'No documents yet'}</h3>
          <p className="subtitle">{latestDocumentSubtitle}</p>
          {ocrAvailable === false && latestDocument && (
            <p className="subtitle" style={{ color: '#ff9800', fontSize: '0.85rem', marginTop: '0.25rem' }}>
              ⚠️ OCR unavailable - scanned/image documents may not extract text
            </p>
          )}
        </div>
        <button
          className="ghost-button compact"
          type="button"
          onClick={onSummarizeLatestDocument}
          disabled={summarizeDisabled}
          title={summarizeTitle}
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
          onClick={onReviewLatestRecord}
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
            {activeMedications
              ? `${activeMedications} active medication${activeMedications === 1 ? '' : 's'}`
              : 'No active medications'}
          </h3>
          <p className="subtitle">{recentMedicationSummary}</p>
        </div>
      </div>
    </div>
  );
}

export default FocusAreasPanel;
