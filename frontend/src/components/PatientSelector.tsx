import { useEffect, useMemo, useState } from 'react';
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
  const [highlightedIndex, setHighlightedIndex] = useState(selectedIndex >= 0 ? selectedIndex : 0);

  useEffect(() => {
    if (selectedIndex >= 0) {
      setHighlightedIndex(selectedIndex);
    } else {
      setHighlightedIndex(0);
    }
  }, [selectedIndex, patientIds.length]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!patients.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex((prev) => Math.min(prev + 1, patients.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const target = patients[highlightedIndex];
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
          patients[highlightedIndex] ? `patient-option-${patients[highlightedIndex].id}` : undefined
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
                patientIds[highlightedIndex] === patient.id ? ' focused' : ''
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
