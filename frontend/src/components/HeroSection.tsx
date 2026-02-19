import type { PatientSummary } from '../types';
import PatientSelector from './PatientSelector';
import BrainVisualization from './BrainVisualization';

type BackendStatus = 'checking' | 'online' | 'offline';
type FeatureIconName = 'document' | 'analysis' | 'chat' | 'trend';

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
  backendStatus: BackendStatus;
};

const features = [
  {
    icon: 'document' as FeatureIconName,
    title: 'Upload Any Document',
    description: 'Lab reports, prescriptions, discharge summaries, imaging reports',
  },
  {
    icon: 'analysis' as FeatureIconName,
    title: 'AI-Powered Analysis',
    description: 'MedGemma extracts and understands your medical data',
  },
  {
    icon: 'chat' as FeatureIconName,
    title: 'Ask Questions',
    description: '"What\'s my A1C trend?" "When was my last checkup?"',
  },
  {
    icon: 'trend' as FeatureIconName,
    title: 'Track Trends',
    description: 'See how your health metrics change over time',
  },
];

const trustSignals = [
  'Private by default',
  'Encrypted in transit',
  'Local-first architecture',
];
const impactStats = [
  { label: 'Record types supported', value: '20+' },
  { label: 'Answer style', value: 'Grounded + cited' },
  { label: 'Setup time', value: '< 2 min' },
];

const FeatureIcon = ({ name }: { name: FeatureIconName }) => {
  if (name === 'document') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 2h8l5 5v13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M16 2v6h6" fill="none" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  if (name === 'analysis') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M9 12h6M12 9v6" fill="none" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  if (name === 'chat') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 5h16v11H8l-4 4V5z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 17l5-5 4 3 7-8" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M18 7h2v2" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
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
  backendStatus,
}: HeroSectionProps) => {
  const authDisabled = backendStatus !== 'online';
  const authStatusMessage = backendStatus === 'offline'
    ? 'Backend is currently offline. Sign-in and account actions are temporarily unavailable.'
    : 'Checking backend connectivity. Sign-in and account actions will enable automatically once available.';
  const handleOpenSignup = () => {
    window.dispatchEvent(new CustomEvent('medmemory:open-signup'));
    const trigger = document.querySelector('[data-testid="open-signup"]') as HTMLButtonElement | null;
    trigger?.click();
  };

  const handleOpenLogin = () => {
    window.dispatchEvent(new CustomEvent('medmemory:open-login'));
    const trigger = document.querySelector('[data-testid="open-login"]') as HTMLButtonElement | null;
    trigger?.click();
  };

  if (!isAuthenticated) {
    return (
      <section className="landing-hero">
        <div className="landing-hero-top">
          <div className="landing-content">
            <div className="landing-brand">
              <BrainVisualization />
              <p className="landing-brand-note">Patient-controlled access</p>
            </div>
            <p className="landing-eyebrow">Private health copilot</p>
            <h1 className="landing-headline">
              Your health records,
              <span className="accent"> finally understood.</span>
            </h1>

            <p className="landing-subheadline">
              Bring labs, prescriptions, and notes into one place. Ask plain-English questions and get grounded answers.
            </p>

            <div className="landing-impact-row" aria-label="Product highlights">
              {impactStats.map((stat) => (
                <span key={stat.label} className="landing-impact-pill">
                  <strong>{stat.value}</strong>
                  <small>{stat.label}</small>
                </span>
              ))}
            </div>

            <div className="landing-role-grid">
              <section className="landing-role-card patient">
                <div className="landing-card-header">
                  <span className="landing-card-tag">For patients</span>
                  <h3>Build your record timeline</h3>
                  <p>Upload records, chat with your history, and track trends over time.</p>
                </div>
                <div className="landing-card-actions">
                  <button
                    className="primary-button large"
                    type="button"
                    onClick={handleOpenSignup}
                    disabled={authDisabled}
                  >
                    Create Patient Account
                  </button>
                  <button
                    className="link-button subtle landing-auth-link"
                    type="button"
                    onClick={handleOpenLogin}
                    disabled={authDisabled}
                  >
                    Already have an account? Sign in
                  </button>
                </div>
              </section>
              <section className="landing-role-card clinician">
                <div className="landing-card-header">
                  <span className="landing-card-tag">For clinicians</span>
                  <h3>Review chart context fast</h3>
                  <p>Open approved patient workspaces and use concise, technical chart chat.</p>
                </div>
                <div className="landing-card-actions">
                  <a className="secondary-button large" href="/clinician">
                    Open Clinician Portal
                  </a>
                </div>
              </section>
            </div>

            <div className="landing-trust-row" aria-label="Trust signals">
              {trustSignals.map((signal) => (
                <span key={signal} className="landing-trust-pill">
                  <span className="trust-dot" aria-hidden />
                  {signal}
                </span>
              ))}
            </div>

            {authDisabled ? (
              <p className="landing-backend-status" role="status" aria-live="polite">
                {authStatusMessage}
              </p>
            ) : null}
          </div>
        </div>

        <div className="landing-features">
          {features.map((feature) => (
            <div key={feature.title} className="landing-feature">
              <span className="feature-icon" aria-hidden>
                <FeatureIcon name={feature.icon} />
              </span>
              <div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="landing-examples">
          <p className="eyebrow">What you can ask</p>
          <div className="example-queries">
            <span className="example-query">"What medications am I on?"</span>
            <span className="example-query">"Show my cholesterol trend"</span>
            <span className="example-query">"Summarize my last visit"</span>
            <span className="example-query">"Compare labs to last year"</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="hero authenticated">
      <div className="hero-copy">
        <p className="eyebrow">Welcome back</p>
        <h1>
          {selectedPatient?.full_name || 'Your Health Dashboard'}
        </h1>
        <p className="subtitle">
          Chat with your complete health timeline, find insights across labs, medications,
          and documents.
        </p>
        {selectedPatient ? (
          <div className="patient-card">
            <strong>{selectedPatient.full_name}</strong>
            <span>Age {selectedPatient.age ?? '—'} · {selectedPatient.gender ?? 'unspecified'}</span>
          </div>
        ) : isLoading ? (
          <div className="patient-card skeleton-card" aria-hidden="true" />
        ) : null}
        <PatientSelector
          patients={patients}
          searchValue={searchValue}
          isLoading={isSearchLoading}
          selectedPatientId={selectedPatientId}
          onSearchChange={onSearchChange}
          onSelectPatient={onSelectPatient}
        />
      </div>
    </section>
  );
};

export default HeroSection;
