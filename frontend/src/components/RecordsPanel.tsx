import type { FormEvent } from 'react';
import type { MedicalRecord } from '../types';

type RecordsPanelProps = {
  records: MedicalRecord[];
  isLoading: boolean;
  recordCount: number;
  formData: { title: string; content: string; record_type: string };
  isSubmitting: boolean;
  isDisabled?: boolean;
  onFormChange: (field: 'title' | 'content' | 'record_type', value: string) => void;
  onSubmit: (event: FormEvent) => void;
  formatDate: (value: string) => string;
};

const RecordsPanel = ({
  records,
  isLoading,
  recordCount,
  formData,
  isSubmitting,
  isDisabled = false,
  onFormChange,
  onSubmit,
  formatDate,
}: RecordsPanelProps) => {
  return (
    <div className="panel records">
      <div className="panel-header">
        <h2>Clinical notes</h2>
        <span className="signal-chip">{isLoading ? '...' : `${recordCount} total`}</span>
      </div>
      <form className="record-form" onSubmit={onSubmit}>
        <div className="form-row">
          <input
            type="text"
            placeholder="Record title"
            value={formData.title}
            onChange={(event) => onFormChange('title', event.target.value)}
            required
            disabled={isSubmitting || isDisabled}
          />
          <select
            value={formData.record_type}
            onChange={(event) => onFormChange('record_type', event.target.value)}
            disabled={isSubmitting || isDisabled}
          >
            <option value="general">General</option>
            <option value="lab_result">Lab Result</option>
            <option value="prescription">Prescription</option>
            <option value="diagnosis">Diagnosis</option>
            <option value="visit_note">Visit Note</option>
            <option value="imaging">Imaging</option>
          </select>
        </div>
        <textarea
          placeholder="Summarize the clinical entry"
          value={formData.content}
          onChange={(event) => onFormChange('content', event.target.value)}
          required
          disabled={isSubmitting || isDisabled}
        />
        <button className="primary-button full" type="submit" disabled={isSubmitting || isDisabled}>
          {isSubmitting ? 'Saving...' : 'Save Record'}
        </button>
      </form>
      <div className="records-list">
        {isDisabled ? (
          <div className="empty-state">Select a patient to view records.</div>
        ) : isLoading ? (
          <>
            <div className="skeleton-card" />
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </>
        ) : records.length === 0 ? (
          <div className="empty-state">No clinical notes yet. Add one to get started.</div>
        ) : (
          records.map((record) => (
            <div key={record.id} className="record-row">
              <div>
                <p className="record-title">{record.title}</p>
                <p className="record-meta">
                  {record.record_type} · {formatDate(record.created_at)}
                </p>
              </div>
              <span className="record-patient">Patient {record.patient_id}</span>
              <p className="record-body">{record.content}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default RecordsPanel;
