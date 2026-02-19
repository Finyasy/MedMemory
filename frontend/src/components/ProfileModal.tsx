import { useState, useEffect, useCallback } from 'react';
import { api, buildBackendUrl } from '../api';
import './ProfileModal.css';

type ProfileData = {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string | null;
  age: number | null;
  sex: string | null;
  gender: string | null;
  blood_type: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  emergency_contacts: EmergencyContact[];
  allergies: Allergy[];
  conditions: Condition[];
  family_history?: FamilyHistoryEntry[];
  providers?: Provider[];
  lifestyle?: Lifestyle | null;
  profile_completion?: { overall_percentage: number };
};

type EmergencyContact = {
  id: number;
  name: string;
  relationship: string;
  phone: string;
  is_primary: boolean;
};

type Allergy = {
  id: number;
  allergen: string;
  allergy_type: string;
  severity: string;
  reaction: string | null;
};

type Condition = {
  id: number;
  condition_name: string;
  status: string;
  diagnosed_date: string | null;
};

type FamilyHistoryEntry = {
  id: number;
  relation: string;
  condition: string;
  age_of_onset: number | null;
  is_deceased: boolean;
  notes: string | null;
};

type Provider = {
  id: number;
  provider_type: string;
  specialty: string | null;
  name: string;
  clinic_name: string | null;
  phone: string | null;
  is_primary: boolean;
};

type Lifestyle = {
  id: number;
  smoking_status: string | null;
  smoking_frequency: string | null;
  alcohol_use: string | null;
  exercise_frequency: string | null;
  diet_type: string | null;
  sleep_hours: number | null;
  occupation: string | null;
  stress_level: string | null;
};

type Tab = 'basic' | 'emergency' | 'medical' | 'providers' | 'lifestyle';

type ProfileModalProps = {
  isOpen: boolean;
  onClose: () => void;
  patientId?: number;
};

const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'unknown'];
const SEX_OPTIONS = ['male', 'female', 'other'];
const ALLERGY_TYPES = ['food', 'drug', 'environmental', 'other'];
const SEVERITY_OPTIONS = ['mild', 'moderate', 'severe', 'life_threatening'];
const CONDITION_STATUS = ['active', 'resolved', 'in_remission'];
const FAMILY_RELATIONS = [
  'mother',
  'father',
  'brother',
  'sister',
  'grandmother',
  'grandfather',
  'aunt',
  'uncle',
  'other',
];
const PROVIDER_TYPES = ['pcp', 'specialist', 'dentist', 'pharmacy', 'hospital', 'other'];
const SMOKING_STATUS = ['never', 'former', 'current'];
const ALCOHOL_USE = ['never', 'occasional', 'moderate', 'heavy'];
const EXERCISE_FREQUENCY = ['none', 'light', 'moderate', 'active'];
const STRESS_LEVEL = ['low', 'moderate', 'high'];

const TAB_ICONS: Record<Tab, string> = {
  basic: '👤',
  emergency: '🚨',
  medical: '🏥',
  providers: '👨‍⚕️',
  lifestyle: '🏃',
};

const TAB_LABELS: Record<Tab, string> = {
  basic: 'Basic Info',
  emergency: 'Emergency',
  medical: 'Medical History',
  providers: 'Providers',
  lifestyle: 'Lifestyle',
};

const ProfileModal = ({ isOpen, onClose, patientId }: ProfileModalProps) => {
  const [tab, setTab] = useState<Tab>('basic');
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Form states
  const [basicForm, setBasicForm] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    sex: '',
    blood_type: '',
    height_cm: '',
    weight_kg: '',
    phone: '',
    email: '',
    address: '',
  });

  const [newContact, setNewContact] = useState({ name: '', relationship: '', phone: '', is_primary: false });
  const [newAllergy, setNewAllergy] = useState({ allergen: '', allergy_type: 'drug', severity: 'moderate', reaction: '' });
  const [newCondition, setNewCondition] = useState({ condition_name: '', status: 'active', diagnosed_date: '' });
  const [newFamilyHistory, setNewFamilyHistory] = useState({
    relation: 'mother',
    condition: '',
    age_of_onset: '',
    is_deceased: false,
    notes: '',
  });
  const [newProvider, setNewProvider] = useState({
    provider_type: 'pcp',
    name: '',
    specialty: '',
    clinic_name: '',
    phone: '',
    is_primary: false,
  });
  const [lifestyleForm, setLifestyleForm] = useState({
    smoking_status: '',
    smoking_frequency: '',
    alcohol_use: '',
    exercise_frequency: '',
    diet_type: '',
    sleep_hours: '',
    occupation: '',
    stress_level: '',
  });

  const fetchWithAuth = useCallback(async (url: string, options: RequestInit = {}) => {
    const authHeaders = await api.getAuthHeaders();
    const headers = {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...(options.headers || {}),
    };
    return fetch(buildBackendUrl(url), { ...options, headers });
  }, []);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const url = patientId ? `/api/v1/profile?patient_id=${patientId}` : '/api/v1/profile';
      const res = await fetchWithAuth(url);
      
      if (res.status === 401) {
        throw new Error('Please log in to view your health profile');
      }
      if (res.status === 404) {
        throw new Error('No health profile found. Please create a patient record first.');
      }
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error?.message || 'Failed to load profile');
      }
      
      const data = await res.json();
      setProfile(data);
      setBasicForm({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        date_of_birth: data.date_of_birth || '',
        sex: data.sex || '',
        blood_type: data.blood_type || '',
        height_cm: data.height_cm?.toString() || '',
        weight_kg: data.weight_kg?.toString() || '',
        phone: data.phone || '',
        email: data.email || '',
        address: data.address || '',
      });
      setLifestyleForm({
        smoking_status: data.lifestyle?.smoking_status || '',
        smoking_frequency: data.lifestyle?.smoking_frequency || '',
        alcohol_use: data.lifestyle?.alcohol_use || '',
        exercise_frequency: data.lifestyle?.exercise_frequency || '',
        diet_type: data.lifestyle?.diet_type || '',
        sleep_hours: data.lifestyle?.sleep_hours?.toString() || '',
        occupation: data.lifestyle?.occupation || '',
        stress_level: data.lifestyle?.stress_level || '',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, patientId]);

  useEffect(() => {
    if (isOpen) {
      loadProfile();
    }
  }, [isOpen, loadProfile]);

  const saveBasicProfile = async () => {
    setSaving(true);
    setError('');
    try {
      const url = patientId ? `/api/v1/profile/basic?patient_id=${patientId}` : '/api/v1/profile/basic';
      const body: Record<string, unknown> = {};
      if (basicForm.first_name) body.first_name = basicForm.first_name;
      if (basicForm.last_name) body.last_name = basicForm.last_name;
      if (basicForm.date_of_birth) body.date_of_birth = basicForm.date_of_birth;
      if (basicForm.sex) body.sex = basicForm.sex;
      if (basicForm.blood_type) body.blood_type = basicForm.blood_type;
      if (basicForm.height_cm) body.height_cm = parseFloat(basicForm.height_cm);
      if (basicForm.weight_kg) body.weight_kg = parseFloat(basicForm.weight_kg);
      if (basicForm.phone) body.phone = basicForm.phone;
      if (basicForm.email) body.email = basicForm.email;
      if (basicForm.address) body.address = basicForm.address;

      const res = await fetchWithAuth(url, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to save profile');
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const addEmergencyContact = async () => {
    if (!newContact.name || !newContact.relationship || !newContact.phone) return;
    setSaving(true);
    try {
      const url = patientId
        ? `/api/v1/profile/emergency-contacts?patient_id=${patientId}`
        : '/api/v1/profile/emergency-contacts';
      const res = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify(newContact),
      });
      if (!res.ok) throw new Error('Failed to add contact');
      setNewContact({ name: '', relationship: '', phone: '', is_primary: false });
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add contact');
    } finally {
      setSaving(false);
    }
  };

  const deleteEmergencyContact = async (contactId: number) => {
    try {
      const url = patientId
        ? `/api/v1/profile/emergency-contacts/${contactId}?patient_id=${patientId}`
        : `/api/v1/profile/emergency-contacts/${contactId}`;
      await fetchWithAuth(url, { method: 'DELETE' });
      await loadProfile();
    } catch {
      setError('Failed to delete contact');
    }
  };

  const addAllergy = async () => {
    if (!newAllergy.allergen) return;
    setSaving(true);
    try {
      const url = patientId ? `/api/v1/profile/allergies?patient_id=${patientId}` : '/api/v1/profile/allergies';
      const res = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify(newAllergy),
      });
      if (!res.ok) throw new Error('Failed to add allergy');
      setNewAllergy({ allergen: '', allergy_type: 'drug', severity: 'moderate', reaction: '' });
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add allergy');
    } finally {
      setSaving(false);
    }
  };

  const deleteAllergy = async (allergyId: number) => {
    try {
      const url = patientId
        ? `/api/v1/profile/allergies/${allergyId}?patient_id=${patientId}`
        : `/api/v1/profile/allergies/${allergyId}`;
      await fetchWithAuth(url, { method: 'DELETE' });
      await loadProfile();
    } catch {
      setError('Failed to delete allergy');
    }
  };

  const addCondition = async () => {
    if (!newCondition.condition_name) return;
    setSaving(true);
    try {
      const url = patientId ? `/api/v1/profile/conditions?patient_id=${patientId}` : '/api/v1/profile/conditions';
      const body: Record<string, unknown> = {
        condition_name: newCondition.condition_name,
        status: newCondition.status,
      };
      if (newCondition.diagnosed_date) body.diagnosed_date = newCondition.diagnosed_date;
      const res = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to add condition');
      setNewCondition({ condition_name: '', status: 'active', diagnosed_date: '' });
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add condition');
    } finally {
      setSaving(false);
    }
  };

  const deleteCondition = async (conditionId: number) => {
    try {
      const url = patientId
        ? `/api/v1/profile/conditions/${conditionId}?patient_id=${patientId}`
        : `/api/v1/profile/conditions/${conditionId}`;
      await fetchWithAuth(url, { method: 'DELETE' });
      await loadProfile();
    } catch {
      setError('Failed to delete condition');
    }
  };

  const addFamilyHistory = async () => {
    if (!newFamilyHistory.condition.trim()) return;
    setSaving(true);
    try {
      const url = patientId ? `/api/v1/profile/family-history?patient_id=${patientId}` : '/api/v1/profile/family-history';
      const body: Record<string, unknown> = {
        relation: newFamilyHistory.relation,
        condition: newFamilyHistory.condition.trim(),
        is_deceased: newFamilyHistory.is_deceased,
      };
      if (newFamilyHistory.age_of_onset) body.age_of_onset = parseInt(newFamilyHistory.age_of_onset, 10);
      if (newFamilyHistory.notes.trim()) body.notes = newFamilyHistory.notes.trim();
      const res = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to add family history');
      setNewFamilyHistory({
        relation: 'mother',
        condition: '',
        age_of_onset: '',
        is_deceased: false,
        notes: '',
      });
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add family history');
    } finally {
      setSaving(false);
    }
  };

  const deleteFamilyHistory = async (historyId: number) => {
    try {
      const url = patientId
        ? `/api/v1/profile/family-history/${historyId}?patient_id=${patientId}`
        : `/api/v1/profile/family-history/${historyId}`;
      await fetchWithAuth(url, { method: 'DELETE' });
      await loadProfile();
    } catch {
      setError('Failed to delete family history');
    }
  };

  const addProvider = async () => {
    if (!newProvider.name) return;
    setSaving(true);
    try {
      const url = patientId ? `/api/v1/profile/providers?patient_id=${patientId}` : '/api/v1/profile/providers';
      const body: Record<string, unknown> = {
        provider_type: newProvider.provider_type,
        name: newProvider.name,
        is_primary: newProvider.is_primary,
      };
      if (newProvider.specialty) body.specialty = newProvider.specialty;
      if (newProvider.clinic_name) body.clinic_name = newProvider.clinic_name;
      if (newProvider.phone) body.phone = newProvider.phone;
      const res = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to add provider');
      setNewProvider({
        provider_type: 'pcp',
        name: '',
        specialty: '',
        clinic_name: '',
        phone: '',
        is_primary: false,
      });
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add provider');
    } finally {
      setSaving(false);
    }
  };

  const deleteProvider = async (providerId: number) => {
    try {
      const url = patientId ? `/api/v1/profile/providers/${providerId}?patient_id=${patientId}` : `/api/v1/profile/providers/${providerId}`;
      await fetchWithAuth(url, { method: 'DELETE' });
      await loadProfile();
    } catch {
      setError('Failed to delete provider');
    }
  };

  const saveLifestyle = async () => {
    setSaving(true);
    setError('');
    try {
      const url = patientId ? `/api/v1/profile/lifestyle?patient_id=${patientId}` : '/api/v1/profile/lifestyle';
      const body: Record<string, unknown> = {};
      if (lifestyleForm.smoking_status) body.smoking_status = lifestyleForm.smoking_status;
      if (lifestyleForm.smoking_frequency) body.smoking_frequency = lifestyleForm.smoking_frequency;
      if (lifestyleForm.alcohol_use) body.alcohol_use = lifestyleForm.alcohol_use;
      if (lifestyleForm.exercise_frequency) body.exercise_frequency = lifestyleForm.exercise_frequency;
      if (lifestyleForm.diet_type) body.diet_type = lifestyleForm.diet_type;
      if (lifestyleForm.sleep_hours !== '') body.sleep_hours = parseFloat(lifestyleForm.sleep_hours);
      if (lifestyleForm.occupation) body.occupation = lifestyleForm.occupation;
      if (lifestyleForm.stress_level) body.stress_level = lifestyleForm.stress_level;

      const res = await fetchWithAuth(url, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to save lifestyle');
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save lifestyle');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const renderLoadingSkeleton = () => (
    <div className="profile-loading">
      <div className="profile-loading-avatar">
        <div className="skeleton-circle" />
      </div>
      <div className="profile-loading-content">
        <div className="skeleton-line skeleton-title" />
        <div className="skeleton-line skeleton-subtitle" />
      </div>
      <div className="skeleton-form">
        <div className="skeleton-row">
          <div className="skeleton-field" />
          <div className="skeleton-field" />
        </div>
        <div className="skeleton-row">
          <div className="skeleton-field" />
          <div className="skeleton-field" />
          <div className="skeleton-field" />
        </div>
        <div className="skeleton-row">
          <div className="skeleton-field" />
          <div className="skeleton-field" />
        </div>
      </div>
    </div>
  );

  const renderErrorState = () => (
    <div className="profile-error-state">
      <div className="error-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <circle cx="12" cy="16" r="0.5" fill="currentColor" />
        </svg>
      </div>
      <h3>Unable to Load Profile</h3>
      <p>{error || 'Something went wrong while loading your health profile.'}</p>
      <div className="error-actions">
        <button className="primary-button" onClick={loadProfile}>
          Try Again
        </button>
        <button className="secondary-button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );

  const getInitials = () => {
    if (profile?.first_name && profile?.last_name) {
      return `${profile.first_name[0]}${profile.last_name[0]}`.toUpperCase();
    }
    return '?';
  };

  return (
    <div className="profile-modal-overlay" onClick={onClose}>
      <div className="profile-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="profile-modal-header">
          <div className="profile-header-left">
            <div className="profile-avatar">
              {profile ? getInitials() : '?'}
            </div>
            <div className="profile-header-info">
              <h2>{profile?.full_name || 'Health Profile'}</h2>
              {profile?.age && profile?.sex && (
                <span className="profile-meta">
                  {profile.age} years old · {profile.sex.charAt(0).toUpperCase() + profile.sex.slice(1)}
                  {profile.blood_type && profile.blood_type !== 'unknown' && ` · ${profile.blood_type}`}
                </span>
              )}
            </div>
          </div>
          
          <div className="profile-header-right">
            {profile?.profile_completion && (
              <div className="profile-completion-badge">
                <div className="completion-ring">
                  <svg viewBox="0 0 36 36">
                    <path
                      className="completion-ring-bg"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="completion-ring-fill"
                      strokeDasharray={`${profile.profile_completion.overall_percentage}, 100`}
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="completion-pct">{profile.profile_completion.overall_percentage}%</span>
                </div>
                <span className="completion-label">Complete</span>
              </div>
            )}
            <button className="profile-close-btn" onClick={onClose} aria-label="Close">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="profile-tabs-container">
          <div className="profile-tabs-scroll">
            {(['basic', 'emergency', 'medical', 'providers', 'lifestyle'] as Tab[]).map((t) => (
              <button
                key={t}
                className={`profile-tab ${tab === t ? 'active' : ''}`}
                onClick={() => setTab(t)}
              >
                <span className="tab-icon">{TAB_ICONS[t]}</span>
                <span className="tab-label">{TAB_LABELS[t]}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="profile-modal-body">
          {loading ? (
            renderLoadingSkeleton()
          ) : error && !profile ? (
            renderErrorState()
          ) : (
            <>
              {error && (
                <div className="profile-inline-error">
                  <span>{error}</span>
                  <button onClick={() => setError('')}>Dismiss</button>
                </div>
              )}

              {tab === 'basic' && (
                <div className="profile-section">
                  <div className="section-header">
                    <h3>Personal Information</h3>
                    <p>Keep your basic health information up to date for better AI insights.</p>
                  </div>

                  <div className="form-grid">
                    <div className="form-group">
                      <label>First Name</label>
                      <input
                        type="text"
                        value={basicForm.first_name}
                        onChange={(e) => setBasicForm({ ...basicForm, first_name: e.target.value })}
                        placeholder="Enter first name"
                      />
                    </div>
                    <div className="form-group">
                      <label>Last Name</label>
                      <input
                        type="text"
                        value={basicForm.last_name}
                        onChange={(e) => setBasicForm({ ...basicForm, last_name: e.target.value })}
                        placeholder="Enter last name"
                      />
                    </div>
                  </div>

                  <div className="form-grid form-grid-3">
                    <div className="form-group">
                      <label>Date of Birth</label>
                      <input
                        type="date"
                        value={basicForm.date_of_birth}
                        onChange={(e) => setBasicForm({ ...basicForm, date_of_birth: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Sex</label>
                      <select
                        value={basicForm.sex}
                        onChange={(e) => setBasicForm({ ...basicForm, sex: e.target.value })}
                      >
                        <option value="">Select...</option>
                        {SEX_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Blood Type</label>
                      <select
                        value={basicForm.blood_type}
                        onChange={(e) => setBasicForm({ ...basicForm, blood_type: e.target.value })}
                      >
                        <option value="">Select...</option>
                        {BLOOD_TYPES.map((bt) => (
                          <option key={bt} value={bt}>
                            {bt === 'unknown' ? "Don't know" : bt}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="form-grid">
                    <div className="form-group">
                      <label>Height</label>
                      <div className="input-with-unit">
                        <input
                          type="number"
                          value={basicForm.height_cm}
                          onChange={(e) => setBasicForm({ ...basicForm, height_cm: e.target.value })}
                          placeholder="170"
                        />
                        <span className="input-unit">cm</span>
                      </div>
                    </div>
                    <div className="form-group">
                      <label>Weight</label>
                      <div className="input-with-unit">
                        <input
                          type="number"
                          value={basicForm.weight_kg}
                          onChange={(e) => setBasicForm({ ...basicForm, weight_kg: e.target.value })}
                          placeholder="70"
                        />
                        <span className="input-unit">kg</span>
                      </div>
                    </div>
                  </div>

                  <div className="form-divider" />

                  <div className="section-header">
                    <h3>Contact Information</h3>
                  </div>

                  <div className="form-grid">
                    <div className="form-group">
                      <label>Phone Number</label>
                      <input
                        type="tel"
                        value={basicForm.phone}
                        onChange={(e) => setBasicForm({ ...basicForm, phone: e.target.value })}
                        placeholder="+1 (555) 123-4567"
                      />
                    </div>
                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        value={basicForm.email}
                        onChange={(e) => setBasicForm({ ...basicForm, email: e.target.value })}
                        placeholder="you@example.com"
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Address</label>
                    <textarea
                      value={basicForm.address}
                      onChange={(e) => setBasicForm({ ...basicForm, address: e.target.value })}
                      rows={2}
                      placeholder="Street address, City, State, ZIP"
                    />
                  </div>

                  <div className="form-actions">
                    <button className="primary-button" onClick={saveBasicProfile} disabled={saving}>
                      {saving ? (
                        <>
                          <span className="button-spinner" />
                          Saving...
                        </>
                      ) : (
                        'Save Changes'
                      )}
                    </button>
                  </div>
                </div>
              )}

              {tab === 'emergency' && (
                <div className="profile-section">
                  <div className="section-header">
                    <h3>Emergency Contacts</h3>
                    <p>People to contact in case of a medical emergency.</p>
                  </div>

                  <div className="items-list">
                    {profile?.emergency_contacts?.map((contact) => (
                      <div key={contact.id} className="list-item">
                        <div className="item-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                        </div>
                        <div className="item-info">
                          <div className="item-title">
                            <strong>{contact.name}</strong>
                            {contact.is_primary && <span className="badge badge-primary">Primary</span>}
                          </div>
                          <span className="item-meta">
                            {contact.relationship} · {contact.phone}
                          </span>
                        </div>
                        <button className="delete-btn" onClick={() => deleteEmergencyContact(contact.id)} title="Remove">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        </button>
                      </div>
                    ))}
                    {!profile?.emergency_contacts?.length && (
                      <div className="empty-list">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                          <circle cx="9" cy="7" r="4" />
                          <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
                        </svg>
                        <span>No emergency contacts added yet</span>
                      </div>
                    )}
                  </div>

                  <div className="add-form">
                    <div className="add-form-header">
                      <span className="add-icon">+</span>
                      <h4>Add Emergency Contact</h4>
                    </div>
                    <div className="form-grid form-grid-3">
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Contact name"
                          value={newContact.name}
                          onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Relationship"
                          value={newContact.relationship}
                          onChange={(e) => setNewContact({ ...newContact, relationship: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <input
                          type="tel"
                          placeholder="Phone number"
                          value={newContact.phone}
                          onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="add-form-footer">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={newContact.is_primary}
                          onChange={(e) => setNewContact({ ...newContact, is_primary: e.target.checked })}
                        />
                        <span>Set as primary contact</span>
                      </label>
                      <button className="secondary-button" onClick={addEmergencyContact} disabled={saving || !newContact.name || !newContact.phone}>
                        Add Contact
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'medical' && (
                <div className="profile-section">
                  <div className="section-header">
                    <h3>Allergies</h3>
                    <p>Record any known allergies for safer medical care.</p>
                  </div>

                  <div className="items-list">
                    {profile?.allergies?.map((allergy) => (
                      <div key={allergy.id} className={`list-item severity-${allergy.severity}`}>
                        <div className="item-icon allergy-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                            <line x1="12" y1="9" x2="12" y2="13" />
                            <line x1="12" y1="17" x2="12.01" y2="17" />
                          </svg>
                        </div>
                        <div className="item-info">
                          <div className="item-title">
                            <strong>{allergy.allergen}</strong>
                            <span className={`badge badge-severity badge-${allergy.severity}`}>
                              {allergy.severity.replace('_', ' ')}
                            </span>
                          </div>
                          <span className="item-meta">{allergy.allergy_type}</span>
                          {allergy.reaction && <span className="item-note">Reaction: {allergy.reaction}</span>}
                        </div>
                        <button className="delete-btn" onClick={() => deleteAllergy(allergy.id)} title="Remove">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        </button>
                      </div>
                    ))}
                    {!profile?.allergies?.length && (
                      <div className="empty-list">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                        <span>No allergies recorded</span>
                      </div>
                    )}
                  </div>

                  <div className="add-form">
                    <div className="add-form-header">
                      <span className="add-icon">+</span>
                      <h4>Add Allergy</h4>
                    </div>
                    <div className="form-grid form-grid-3">
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Allergen (e.g., Penicillin)"
                          value={newAllergy.allergen}
                          onChange={(e) => setNewAllergy({ ...newAllergy, allergen: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <select
                          value={newAllergy.allergy_type}
                          onChange={(e) => setNewAllergy({ ...newAllergy, allergy_type: e.target.value })}
                        >
                          {ALLERGY_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t.charAt(0).toUpperCase() + t.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <select
                          value={newAllergy.severity}
                          onChange={(e) => setNewAllergy({ ...newAllergy, severity: e.target.value })}
                        >
                          {SEVERITY_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s.replace('_', ' ').charAt(0).toUpperCase() + s.replace('_', ' ').slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="form-group">
                      <input
                        type="text"
                        placeholder="Reaction description (optional)"
                        value={newAllergy.reaction}
                        onChange={(e) => setNewAllergy({ ...newAllergy, reaction: e.target.value })}
                      />
                    </div>
                    <div className="add-form-footer">
                      <button className="secondary-button" onClick={addAllergy} disabled={saving || !newAllergy.allergen}>
                        Add Allergy
                      </button>
                    </div>
                  </div>

                  <div className="form-divider" />

                  <div className="section-header">
                    <h3>Chronic Conditions</h3>
                    <p>Long-term health conditions that affect your care.</p>
                  </div>

                  <div className="items-list">
                    {profile?.conditions?.map((condition) => (
                      <div key={condition.id} className="list-item">
                        <div className="item-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                          </svg>
                        </div>
                        <div className="item-info">
                          <div className="item-title">
                            <strong>{condition.condition_name}</strong>
                            <span className={`badge badge-status badge-${condition.status}`}>
                              {condition.status.replace('_', ' ')}
                            </span>
                          </div>
                          {condition.diagnosed_date && (
                            <span className="item-meta">Diagnosed: {condition.diagnosed_date}</span>
                          )}
                        </div>
                        <button className="delete-btn" onClick={() => deleteCondition(condition.id)} title="Remove">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        </button>
                      </div>
                    ))}
                    {!profile?.conditions?.length && (
                      <div className="empty-list">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M9 12h6M12 9v6M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
                        </svg>
                        <span>No chronic conditions recorded</span>
                      </div>
                    )}
                  </div>

                  <div className="add-form">
                    <div className="add-form-header">
                      <span className="add-icon">+</span>
                      <h4>Add Condition</h4>
                    </div>
                    <div className="form-grid form-grid-3">
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Condition name"
                          value={newCondition.condition_name}
                          onChange={(e) => setNewCondition({ ...newCondition, condition_name: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <select
                          value={newCondition.status}
                          onChange={(e) => setNewCondition({ ...newCondition, status: e.target.value })}
                        >
                          {CONDITION_STATUS.map((s) => (
                            <option key={s} value={s}>
                              {s.replace('_', ' ').charAt(0).toUpperCase() + s.replace('_', ' ').slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <input
                          type="date"
                          placeholder="Diagnosed date"
                          value={newCondition.diagnosed_date}
                          onChange={(e) => setNewCondition({ ...newCondition, diagnosed_date: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="add-form-footer">
                      <button className="secondary-button" onClick={addCondition} disabled={saving || !newCondition.condition_name}>
                        Add Condition
                      </button>
                    </div>
                  </div>

                  <div className="form-divider" />

                  <div className="section-header">
                    <h3>Family History</h3>
                    <p>Add family risk factors used to prioritize dashboard highlights (not diagnosis).</p>
                  </div>

                  <div className="items-list">
                    {profile?.family_history?.map((entry) => (
                      <div key={entry.id} className="list-item">
                        <div className="item-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                            <circle cx="8.5" cy="7" r="4" />
                            <path d="M20 8v6M23 11h-6" />
                          </svg>
                        </div>
                        <div className="item-info">
                          <div className="item-title">
                            <strong>{entry.condition}</strong>
                            <span className="badge badge-status">{entry.relation}</span>
                          </div>
                          {entry.age_of_onset != null ? (
                            <span className="item-meta">Onset age: {entry.age_of_onset}</span>
                          ) : null}
                          {entry.notes ? <span className="item-note">{entry.notes}</span> : null}
                        </div>
                        <button className="delete-btn" onClick={() => deleteFamilyHistory(entry.id)} title="Remove">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        </button>
                      </div>
                    ))}
                    {!profile?.family_history?.length && (
                      <div className="empty-list">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                          <circle cx="8.5" cy="7" r="4" />
                          <path d="M20 8v6M23 11h-6" />
                        </svg>
                        <span>No family history entries yet</span>
                      </div>
                    )}
                  </div>

                  <div className="add-form">
                    <div className="add-form-header">
                      <span className="add-icon">+</span>
                      <h4>Add Family History</h4>
                    </div>
                    <div className="form-grid form-grid-3">
                      <div className="form-group">
                        <select
                          value={newFamilyHistory.relation}
                          onChange={(e) => setNewFamilyHistory({ ...newFamilyHistory, relation: e.target.value })}
                        >
                          {FAMILY_RELATIONS.map((relation) => (
                            <option key={relation} value={relation}>
                              {relation.charAt(0).toUpperCase() + relation.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Condition (e.g., prostate cancer)"
                          value={newFamilyHistory.condition}
                          onChange={(e) => setNewFamilyHistory({ ...newFamilyHistory, condition: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <input
                          type="number"
                          min="0"
                          max="120"
                          placeholder="Age of onset"
                          value={newFamilyHistory.age_of_onset}
                          onChange={(e) => setNewFamilyHistory({ ...newFamilyHistory, age_of_onset: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <input
                        type="text"
                        placeholder="Notes (optional)"
                        value={newFamilyHistory.notes}
                        onChange={(e) => setNewFamilyHistory({ ...newFamilyHistory, notes: e.target.value })}
                      />
                    </div>
                    <div className="add-form-footer">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={newFamilyHistory.is_deceased}
                          onChange={(e) => setNewFamilyHistory({ ...newFamilyHistory, is_deceased: e.target.checked })}
                        />
                        <span>Relative is deceased</span>
                      </label>
                      <button
                        className="secondary-button"
                        onClick={addFamilyHistory}
                        disabled={saving || !newFamilyHistory.condition.trim()}
                      >
                        Add Family History
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'providers' && (
                <div className="profile-section">
                  <div className="section-header">
                    <h3>Healthcare Providers</h3>
                    <p>Your doctors, specialists, and healthcare facilities.</p>
                  </div>

                  <div className="items-list">
                    {profile?.providers?.map((provider) => (
                      <div key={provider.id} className="list-item">
                        <div className="item-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 9h18v10a2 2 0 01-2 2H5a2 2 0 01-2-2V9zM3 9V7a2 2 0 012-2h14a2 2 0 012 2v2M9 13h6" />
                          </svg>
                        </div>
                        <div className="item-info">
                          <div className="item-title">
                            <strong>{provider.name}</strong>
                            {provider.is_primary && <span className="badge badge-primary">Primary</span>}
                          </div>
                          <span className="item-meta">
                            {provider.provider_type.toUpperCase()}
                            {provider.specialty && ` · ${provider.specialty}`}
                          </span>
                          {provider.clinic_name && <span className="item-note">{provider.clinic_name}</span>}
                          {provider.phone && <span className="item-note">{provider.phone}</span>}
                        </div>
                        <button className="delete-btn" onClick={() => deleteProvider(provider.id)} title="Remove">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        </button>
                      </div>
                    ))}
                    {!profile?.providers?.length && (
                      <div className="empty-list">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M3 9h18v10a2 2 0 01-2 2H5a2 2 0 01-2-2V9zM3 9V7a2 2 0 012-2h14a2 2 0 012 2v2M9 13h6" />
                        </svg>
                        <span>No healthcare providers added yet</span>
                      </div>
                    )}
                  </div>

                  <div className="add-form">
                    <div className="add-form-header">
                      <span className="add-icon">+</span>
                      <h4>Add Provider</h4>
                    </div>
                    <div className="form-grid form-grid-3">
                      <div className="form-group">
                        <select
                          value={newProvider.provider_type}
                          onChange={(e) => setNewProvider({ ...newProvider, provider_type: e.target.value })}
                        >
                          {PROVIDER_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t === 'pcp' ? 'Primary Care' : t.charAt(0).toUpperCase() + t.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Provider name"
                          value={newProvider.name}
                          onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Specialty (optional)"
                          value={newProvider.specialty}
                          onChange={(e) => setNewProvider({ ...newProvider, specialty: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="form-grid">
                      <div className="form-group">
                        <input
                          type="text"
                          placeholder="Clinic name (optional)"
                          value={newProvider.clinic_name}
                          onChange={(e) => setNewProvider({ ...newProvider, clinic_name: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <input
                          type="tel"
                          placeholder="Phone number (optional)"
                          value={newProvider.phone}
                          onChange={(e) => setNewProvider({ ...newProvider, phone: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="add-form-footer">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={newProvider.is_primary}
                          onChange={(e) => setNewProvider({ ...newProvider, is_primary: e.target.checked })}
                        />
                        <span>Set as primary provider</span>
                      </label>
                      <button className="secondary-button" onClick={addProvider} disabled={saving || !newProvider.name}>
                        Add Provider
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'lifestyle' && (
                <div className="profile-section">
                  <div className="section-header">
                    <h3>Lifestyle Factors</h3>
                    <p>Help us provide better personalized health insights.</p>
                  </div>

                  <div className="lifestyle-grid">
                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">🚬</div>
                      <div className="lifestyle-card-content">
                        <h4>Smoking</h4>
                        <div className="form-grid">
                          <div className="form-group">
                            <label>Status</label>
                            <select
                              value={lifestyleForm.smoking_status}
                              onChange={(e) => setLifestyleForm({ ...lifestyleForm, smoking_status: e.target.value })}
                            >
                              <option value="">Select...</option>
                              {SMOKING_STATUS.map((s) => (
                                <option key={s} value={s}>
                                  {s.charAt(0).toUpperCase() + s.slice(1)}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="form-group">
                            <label>Frequency</label>
                            <input
                              type="text"
                              placeholder="e.g. 1 pack/day"
                              value={lifestyleForm.smoking_frequency}
                              onChange={(e) => setLifestyleForm({ ...lifestyleForm, smoking_frequency: e.target.value })}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">🍷</div>
                      <div className="lifestyle-card-content">
                        <h4>Alcohol</h4>
                        <div className="form-group">
                          <label>Consumption</label>
                          <select
                            value={lifestyleForm.alcohol_use}
                            onChange={(e) => setLifestyleForm({ ...lifestyleForm, alcohol_use: e.target.value })}
                          >
                            <option value="">Select...</option>
                            {ALCOHOL_USE.map((s) => (
                              <option key={s} value={s}>
                                {s.charAt(0).toUpperCase() + s.slice(1)}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">🏃</div>
                      <div className="lifestyle-card-content">
                        <h4>Exercise</h4>
                        <div className="form-group">
                          <label>Frequency</label>
                          <select
                            value={lifestyleForm.exercise_frequency}
                            onChange={(e) => setLifestyleForm({ ...lifestyleForm, exercise_frequency: e.target.value })}
                          >
                            <option value="">Select...</option>
                            {EXERCISE_FREQUENCY.map((s) => (
                              <option key={s} value={s}>
                                {s.charAt(0).toUpperCase() + s.slice(1)}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">🥗</div>
                      <div className="lifestyle-card-content">
                        <h4>Diet</h4>
                        <div className="form-group">
                          <label>Type</label>
                          <input
                            type="text"
                            placeholder="e.g. Mediterranean, Vegetarian"
                            value={lifestyleForm.diet_type}
                            onChange={(e) => setLifestyleForm({ ...lifestyleForm, diet_type: e.target.value })}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">😴</div>
                      <div className="lifestyle-card-content">
                        <h4>Sleep</h4>
                        <div className="form-group">
                          <label>Hours per night</label>
                          <div className="input-with-unit">
                            <input
                              type="number"
                              min="0"
                              max="24"
                              step="0.5"
                              placeholder="7.5"
                              value={lifestyleForm.sleep_hours}
                              onChange={(e) => setLifestyleForm({ ...lifestyleForm, sleep_hours: e.target.value })}
                            />
                            <span className="input-unit">hrs</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="lifestyle-card">
                      <div className="lifestyle-card-icon">💼</div>
                      <div className="lifestyle-card-content">
                        <h4>Work</h4>
                        <div className="form-grid">
                          <div className="form-group">
                            <label>Occupation</label>
                            <input
                              type="text"
                              placeholder="e.g. Software Engineer"
                              value={lifestyleForm.occupation}
                              onChange={(e) => setLifestyleForm({ ...lifestyleForm, occupation: e.target.value })}
                            />
                          </div>
                          <div className="form-group">
                            <label>Stress Level</label>
                            <select
                              value={lifestyleForm.stress_level}
                              onChange={(e) => setLifestyleForm({ ...lifestyleForm, stress_level: e.target.value })}
                            >
                              <option value="">Select...</option>
                              {STRESS_LEVEL.map((s) => (
                                <option key={s} value={s}>
                                  {s.charAt(0).toUpperCase() + s.slice(1)}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button className="primary-button" onClick={saveLifestyle} disabled={saving}>
                      {saving ? (
                        <>
                          <span className="button-spinner" />
                          Saving...
                        </>
                      ) : (
                        'Save Lifestyle'
                      )}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfileModal;
