import type { PatientSummary } from '../types';
import PatientSelector from './PatientSelector';
import BrainVisualization from './BrainVisualization';

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

const features = [
  {
    icon: '📋',
    title: 'Upload Any Document',
    description: 'Lab reports, prescriptions, discharge summaries, imaging reports',
  },
  {
    icon: '🧠',
    title: 'AI-Powered Analysis',
    description: 'MedGemma extracts and understands your medical data',
  },
  {
    icon: '💬',
    title: 'Ask Questions',
    description: '"What\'s my A1C trend?" "When was my last checkup?"',
  },
  {
    icon: '📈',
    title: 'Track Trends',
    description: 'See how your health metrics change over time',
  },
];

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
  const handleOpenSignup = () => {
    const btn = document.querySelector('[data-testid="open-signup"]') as HTMLButtonElement;
    btn?.click();
  };

  const handleOpenLogin = () => {
    const btn = document.querySelector('[data-testid="open-login"]') as HTMLButtonElement;
    btn?.click();
  };

  if (!isAuthenticated) {
    return (
      <section className="landing-hero">
        <div className="landing-brand">
          <BrainVisualization />
        </div>
        
        <div className="landing-content">
          <h1 className="landing-headline">
            Your health records,
            <span className="accent"> finally understood.</span>
          </h1>
          
          <p className="landing-subheadline">
            Upload medical documents, ask questions in plain English, and get instant answers powered by AI.
          </p>

          <div className="landing-cta">
            <button className="primary-button large" type="button" onClick={handleOpenSignup}>
              Get Started Free
            </button>
            <button className="secondary-button large" type="button" onClick={handleOpenLogin}>
              Sign In
            </button>
          </div>

          <p className="landing-trust">
            Secure, private, and local-first. Your data stays yours.
          </p>
        </div>

        <div className="landing-features">
          {features.map((feature) => (
            <div key={feature.title} className="landing-feature">
              <span className="feature-icon">{feature.icon}</span>
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
