import { useMemo, useState } from 'react';
import type { PatientSummary } from '../types';

type PatientSelectorProps = {
  patients: PatientSummary[];
  searchValue: string;
  isLoading: boolean;
  selectedPatientId: number;
  onSearchChange: (value: string) => void;
  onSelectPatient: (id: number) => void;
};

const PatientSelector = ({
  patients,
  searchValue,
  isLoading,
  selectedPatientId,
  onSearchChange,
  onSelectPatient,
}: PatientSelectorProps) => {
  const inputId = 'patient-search';
  const patientIds = useMemo(() => patients.map((patient) => patient.id), [patients]);
  const selectedIndex = useMemo(() => patientIds.indexOf(selectedPatientId), [patientIds, selectedPatientId]);
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const activeIndex = useMemo(() => {
    if (!patients.length) return 0;
    if (selectedIndex >= 0) return selectedIndex;
    const fallback = highlightedIndex ?? 0;
    return Math.min(Math.max(fallback, 0), patients.length - 1);
  }, [patients.length, selectedIndex, highlightedIndex]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!patients.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex((prev) => {
        const current = selectedIndex >= 0 ? selectedIndex : (prev ?? 0);
        return Math.min(current + 1, patients.length - 1);
      });
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((prev) => {
        const current = selectedIndex >= 0 ? selectedIndex : (prev ?? 0);
        return Math.max(current - 1, 0);
      });
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const target = patients[activeIndex];
      if (target) onSelectPatient(target.id);
    }
  };

  return (
    <div className="patient-selector">
      <label className="patient-label" htmlFor="patient-search">
        Find a patient
      </label>
      <input
        id={inputId}
        className="patient-search"
        type="text"
        placeholder="Search by name or external ID"
        value={searchValue}
        onChange={(event) => onSearchChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div
        className="patient-list"
        role="listbox"
        aria-label="Patient results"
        aria-activedescendant={
          patients[activeIndex] ? `patient-option-${patients[activeIndex].id}` : undefined
        }
        onKeyDown={handleKeyDown}
      >
        {isLoading ? (
          <>
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </>
        ) : !searchValue.trim() ? (
          <div className="empty-state">Start typing to search patients.</div>
        ) : patients.length === 0 ? (
          <div className="empty-state">No patients match that search.</div>
        ) : (
          patients.map((patient) => (
            <button
              key={patient.id}
              id={`patient-option-${patient.id}`}
              type="button"
              className={`patient-row${patient.id === selectedPatientId ? ' active' : ''}${
                patientIds[activeIndex] === patient.id ? ' focused' : ''
              }`}
              onClick={() => onSelectPatient(patient.id)}
              onMouseEnter={() => setHighlightedIndex(patientIds.indexOf(patient.id))}
              role="option"
              aria-selected={patient.id === selectedPatientId}
            >
              <span className="patient-name">{patient.full_name}</span>
              <span className="patient-meta">
                Age {patient.age ?? '—'} · {patient.gender ?? 'unspecified'}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
};

export default PatientSelector;
