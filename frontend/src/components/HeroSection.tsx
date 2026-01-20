import type { PatientSummary } from '../types';
import PatientSelector from './PatientSelector';

type HeroSectionProps = {
  selectedPatient?: PatientSummary;
  isLoading?: boolean;
  patients: PatientSummary[];
  searchValue: string;
  isSearchLoading: boolean;
  selectedPatientId: number;
  onSearchChange: (value: string) => void;
  onSelectPatient: (id: number) => void;
  isAuthenticated: boolean;
};

const HeroSection = ({
  selectedPatient,
  isLoading = false,
  patients,
  searchValue,
  isSearchLoading,
  selectedPatientId,
  onSearchChange,
  onSelectPatient,
  isAuthenticated,
}: HeroSectionProps) => {
  return (
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">Unified, local-first medical memory</p>
        <h1>
          Clinician-grade answers,
          <span> grounded in your records.</span>
        </h1>
        <p className="subtitle">
          Chat with your complete health timeline, quickly find insights across labs, medications,
          visits, and documents, and get clear, ready-to-use context in seconds.
        </p>
        {selectedPatient ? (
          <div className="patient-card">
            <strong>{selectedPatient.full_name}</strong>
            <span>Age {selectedPatient.age ?? '—'} · {selectedPatient.gender ?? 'unspecified'}</span>
          </div>
        ) : isLoading ? (
          <div className="patient-card skeleton-card" aria-hidden="true" />
        ) : null}
        <div className="hero-actions">
          <button className="primary-button" type="button">Start a RAG Chat</button>
          <button className="secondary-button" type="button">Generate Context</button>
        </div>
        {isAuthenticated ? (
          <PatientSelector
            patients={patients}
            searchValue={searchValue}
            isLoading={isSearchLoading}
            selectedPatientId={selectedPatientId}
            onSearchChange={onSearchChange}
            onSelectPatient={onSelectPatient}
          />
        ) : (
          <div className="empty-state">
            Create an account or sign in to upload your medical reports and chat with your health memory.
          </div>
        )}
        <div className="chip-row">
          {['Labs', 'Medications', 'Encounters', 'Documents', 'Memory'].map((chip) => (
            <span key={chip} className="chip">{chip}</span>
          ))}
        </div>
      </div>
      <div className="hero-card">
        <div className="hero-card-header">
          <div>
            <p className="card-title">LDL Cholesterol</p>
            <p className="card-subtitle">114-167 mg/dL</p>
          </div>
          <span className="signal-chip">Reviewed</span>
        </div>
        <div className="hero-chart">
          <div className="chart-grid" />
          <svg viewBox="0 0 340 140" className="chart-line" role="img" aria-label="LDL trend">
            <path d="M20 30 L90 50 L150 70 L220 80 L300 100" fill="none" stroke="var(--accent-strong)" strokeWidth="3" />
          </svg>
        </div>
        <p className="hero-card-body">
          Latest LDL: 114 mg/dL, trending downward with therapy adjustments.
          Highlighted improvements over the last three panels.
        </p>
        <div className="hero-metrics">
          <div>
            <h3>12</h3>
            <span>Out of range</span>
          </div>
          <div>
            <h3>43</h3>
            <span>In range</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
