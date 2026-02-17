import type { ClinicianAccessRequest } from '../../types';

type ClinicianAccessPanelProps = {
  patientId: number;
  accessRequestsLoading: boolean;
  accessRequests: ClinicianAccessRequest[];
  actingGrantId: number | null;
  onApproveAccess: (grantId: number) => void;
  onDenyAccess: (grantId: number) => void;
};

function ClinicianAccessPanel({
  patientId,
  accessRequestsLoading,
  accessRequests,
  actingGrantId,
  onApproveAccess,
  onDenyAccess,
}: ClinicianAccessPanelProps) {
  return (
    <section className="dashboard-main clinician-access-section">
      <div className="insight-panel clinician-access-panel">
        <div className="clinician-access-header">
          <p className="eyebrow">Clinician access</p>
          <h2>Your Patient ID & access requests</h2>
          <p className="subtitle">
            Share your Patient ID with your clinician so they can request access. Approve or deny requests below.
          </p>
        </div>
        {patientId > 0 && (
          <div className="patient-id-block">
            <strong>Your Patient ID (share with your clinician):</strong>
            <span className="patient-id-value">{patientId}</span>
          </div>
        )}
        <div className="access-requests-block">
          <h3>Access requests</h3>
          {accessRequestsLoading ? (
            <p className="clinician-access-loading">Loading…</p>
          ) : accessRequests.length === 0 ? (
            <p className="clinician-access-empty">No access requests.</p>
          ) : (
            <ul className="access-requests-list">
              {accessRequests.map((req) => (
                <li key={req.grant_id} className={`access-request-item access-request-${req.status}`}>
                  <div className="access-request-info">
                    <strong>{req.clinician_name}</strong>
                    <span className="access-request-meta">{req.clinician_email}</span>
                    <span className="access-request-meta">
                      For: {req.patient_name} · {req.status}
                    </span>
                  </div>
                  {req.status === 'pending' && (
                    <div className="access-request-actions">
                      <button
                        type="button"
                        className="primary-button compact"
                        disabled={actingGrantId !== null}
                        onClick={() => onApproveAccess(req.grant_id)}
                      >
                        {actingGrantId === req.grant_id ? 'Approving…' : 'Approve'}
                      </button>
                      <button
                        type="button"
                        className="secondary-button compact"
                        disabled={actingGrantId !== null}
                        onClick={() => onDenyAccess(req.grant_id)}
                      >
                        Deny
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

export default ClinicianAccessPanel;
