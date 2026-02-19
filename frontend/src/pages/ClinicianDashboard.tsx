import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api';
import useAppStore from '../store/useAppStore';
import type { DocumentItem } from '../types';

type PatientWithGrant = {
  patient_id: number;
  patient_first_name: string;
  patient_last_name: string;
  patient_full_name: string;
  grant_id: number;
  grant_status: string;
  grant_scopes: string;
  granted_at?: string | null;
  expires_at?: string | null;
};

type ClinicianDashboardProps = {
  onSelectPatient: (patientId: number, fullName: string) => void;
  onError: (msg: string, err: unknown) => void;
};

export default function ClinicianDashboard({ onSelectPatient, onError }: ClinicianDashboardProps) {
  const [patients, setPatients] = useState<PatientWithGrant[]>([]);
  const [uploads, setUploads] = useState<DocumentItem[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [loadingUploads, setLoadingUploads] = useState(true);
  const logout = useAppStore((state) => state.logout);

  const load = useCallback(async () => {
    setLoadingPatients(true);
    setLoadingUploads(true);
    try {
      const [patientList, uploadList] = await Promise.all([
        api.listClinicianPatients('active'),
        api.listClinicianUploads({ limit: 50 }),
      ]);
      setPatients(patientList);
      setUploads(uploadList);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        return;
      }
      onError('Failed to load dashboard', err);
    } finally {
      setLoadingPatients(false);
      setLoadingUploads(false);
    }
  }, [logout, onError]);

  useEffect(() => {
    load();
  }, [load]);

  const handleLogout = () => {
    logout();
    window.location.href = '/clinician';
  };

  return (
    <div className="clinician-dashboard">
      <header className="clinician-header">
        <div className="clinician-header-inner">
          <h1>Clinician Dashboard</h1>
          <nav>
            <a href="/">MedMemory</a>
            <button type="button" className="ghost-button" onClick={handleLogout}>
              Log out
            </button>
          </nav>
        </div>
      </header>
      <main className="clinician-main">
        <section className="clinician-section">
          <h2>Patients with access</h2>
          {loadingPatients ? (
            <p className="clinician-loading">Loading…</p>
          ) : patients.length === 0 ? (
            <p className="clinician-empty">No patients with active access. Request access from a patient.</p>
          ) : (
            <ul className="clinician-patient-list">
              {patients.map((p) => (
                <li key={p.grant_id}>
                  <button
                    type="button"
                    className="clinician-patient-card"
                    onClick={() => onSelectPatient(p.patient_id, p.patient_full_name)}
                  >
                    <strong>{p.patient_full_name}</strong>
                    <span className="clinician-meta">Grant: {p.grant_status}</span>
                    {p.expires_at && (
                      <span className="clinician-meta">
                        Expires: {new Date(p.expires_at).toLocaleDateString()}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="clinician-section">
          <h2>Recent uploads</h2>
          {loadingUploads ? (
            <p className="clinician-loading">Loading…</p>
          ) : uploads.length === 0 ? (
            <p className="clinician-empty">No documents yet.</p>
          ) : (
            <ul className="clinician-upload-list">
              {uploads.slice(0, 20).map((doc) => (
                <li key={doc.id}>
                  <span className="clinician-upload-title">{doc.title || doc.original_filename}</span>
                  <span className="clinician-meta">Patient ID: {doc.patient_id}</span>
                  <span className="clinician-meta">{doc.processing_status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
