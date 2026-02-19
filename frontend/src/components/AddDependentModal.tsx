import { useState } from 'react';
import { api } from '../api';
import './AddDependentModal.css';

type AddDependentModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onAdded: (dependentId: number, dependentName: string) => void;
};

const RELATIONSHIP_TYPES = [
  { value: 'child', label: 'Child', icon: '👶' },
  { value: 'spouse', label: 'Spouse', icon: '💑' },
  { value: 'parent', label: 'Parent', icon: '👴' },
  { value: 'sibling', label: 'Sibling', icon: '👫' },
  { value: 'guardian', label: 'Guardian', icon: '🛡️' },
  { value: 'other', label: 'Other', icon: '👤' },
];

const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'unknown'];
const SEX_OPTIONS = ['male', 'female', 'other'];

const AddDependentModal = ({ isOpen, onClose, onAdded }: AddDependentModalProps) => {
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [guardianConfirmed, setGuardianConfirmed] = useState(false);
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    sex: '',
    blood_type: '',
    relationship_type: 'child',
  });

  const handleSubmit = async () => {
    if (!form.first_name || !form.last_name || !form.date_of_birth || !form.relationship_type) {
      setError('Please fill in all required fields');
      return;
    }
    if (!guardianConfirmed) {
      setError('Please confirm you have permission to manage this record.');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const payload: {
        first_name: string;
        last_name: string;
        date_of_birth: string;
        relationship_type: string;
        sex?: string;
        blood_type?: string;
      } = {
        first_name: form.first_name,
        last_name: form.last_name,
        date_of_birth: form.date_of_birth,
        relationship_type: form.relationship_type,
      };
      if (form.sex) payload.sex = form.sex;
      if (form.blood_type) payload.blood_type = form.blood_type;

      const newDependent = await api.createDependent(payload);
      const fullName = `${form.first_name} ${form.last_name}`.trim();
      onAdded(newDependent.id, fullName);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add dependent');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    setStep(1);
    setError('');
    setGuardianConfirmed(false);
    setForm({
      first_name: '',
      last_name: '',
      date_of_birth: '',
      sex: '',
      blood_type: '',
      relationship_type: 'child',
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="add-dependent-overlay" onClick={handleClose}>
      <div className="add-dependent-content" onClick={(e) => e.stopPropagation()}>
        <div className="add-dependent-header">
          <h2>Add Family Member</h2>
          <button className="add-dependent-close" onClick={handleClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && <div className="add-dependent-error">{error}</div>}

        <div className="add-dependent-body">
          {step === 1 && (
            <div className="step-content">
              <p className="step-instruction">Who would you like to add?</p>
              <div className="relationship-grid">
                {RELATIONSHIP_TYPES.map((rel) => (
                  <button
                    key={rel.value}
                    className={`relationship-option ${form.relationship_type === rel.value ? 'selected' : ''}`}
                    onClick={() => setForm({ ...form, relationship_type: rel.value })}
                  >
                    <span className="rel-icon">{rel.icon}</span>
                    <span className="rel-label">{rel.label}</span>
                  </button>
                ))}
              </div>
              <button className="primary-button" onClick={() => setStep(2)}>
                Continue
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="step-content">
              <p className="step-instruction">Enter their details</p>

              <div className="form-row">
                <div className="form-group">
                  <label>
                    First Name <span className="required">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                    placeholder="Enter first name"
                    autoFocus
                  />
                </div>
                <div className="form-group">
                  <label>
                    Last Name <span className="required">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                    placeholder="Enter last name"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>
                    Date of Birth <span className="required">*</span>
                  </label>
                  <input
                    type="date"
                    value={form.date_of_birth}
                    onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Sex</label>
                  <select value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
                    <option value="">Select...</option>
                    {SEX_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Blood Type</label>
                <select value={form.blood_type} onChange={(e) => setForm({ ...form, blood_type: e.target.value })}>
                  <option value="">Select or leave blank if unknown</option>
                  {BLOOD_TYPES.map((bt) => (
                    <option key={bt} value={bt}>
                      {bt === 'unknown' ? "Don't know" : bt}
                    </option>
                  ))}
                </select>
              </div>

              <label className="checkbox-label consent">
                <input
                  type="checkbox"
                  checked={guardianConfirmed}
                  onChange={(e) => setGuardianConfirmed(e.target.checked)}
                />
                I confirm I have permission to manage this person’s health records.
              </label>
              <div className="button-row">
                <button className="ghost-button" onClick={() => setStep(1)}>
                  Back
                </button>
                <button className="primary-button" onClick={handleSubmit} disabled={saving}>
                  {saving ? 'Adding...' : 'Add Family Member'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AddDependentModal;
