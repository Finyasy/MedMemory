import { useEffect, useState } from 'react';
import './App.css';
import { api } from './api';
import type { MedicalRecord } from './types';

function App() {
  const [isOnline, setIsOnline] = useState(false);
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    record_type: 'general',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Check API health
    api.getHealth()
      .then(() => setIsOnline(true))
      .catch(() => setIsOnline(false));

    // Load records
    loadRecords();
  }, []);

  const loadRecords = async () => {
    try {
      const data = await api.getRecords();
      setRecords(data);
    } catch (error) {
      console.error('Failed to load records:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title || !formData.content) return;

    setIsSubmitting(true);
    try {
      await api.createRecord(formData);
      setFormData({ title: '', content: '', record_type: 'general' });
      await loadRecords();
    } catch (error) {
      console.error('Failed to create record:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <div className="logo-icon">🧠</div>
            <h1>MedMemory</h1>
          </div>
          <div className="status-badge">
            <span className={`status-dot ${!isOnline ? 'offline' : ''}`} />
            {isOnline ? 'API Connected' : 'Offline'}
          </div>
        </div>
      </header>

      <main className="main">
        <section className="welcome">
          <h2>Your Medical Memory</h2>
          <p>
            A unified, local-first platform for human-centered electronic health 
            records and intelligent question answering.
          </p>
        </section>

        <div className="cards-grid">
          <div className="card">
            <div className="card-header">
              <div className="card-icon">🔒</div>
              <h3>Local-First Privacy</h3>
            </div>
            <p>
              Your medical data stays on your device. No cloud uploads, 
              no third-party access—complete control over your health information.
            </p>
          </div>
          <div className="card">
            <div className="card-header">
              <div className="card-icon">💬</div>
              <h3>Intelligent Q&A</h3>
            </div>
            <p>
              Ask questions about your medical history in natural language. 
              Get instant, accurate answers from your personal health records.
            </p>
          </div>
          <div className="card">
            <div className="card-header">
              <div className="card-icon">📋</div>
              <h3>Unified Records</h3>
            </div>
            <p>
              Consolidate records from multiple providers into one searchable, 
              organized medical memory that's always accessible.
            </p>
          </div>
        </div>

        <form className="form-section" onSubmit={handleSubmit}>
          <h3>📝 Add Medical Record</h3>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="title">Title</label>
              <input
                id="title"
                type="text"
                placeholder="e.g., Annual Physical Exam"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="record_type">Record Type</label>
              <select
                id="record_type"
                value={formData.record_type}
                onChange={(e) => setFormData({ ...formData, record_type: e.target.value })}
              >
                <option value="general">General</option>
                <option value="lab_result">Lab Result</option>
                <option value="prescription">Prescription</option>
                <option value="diagnosis">Diagnosis</option>
                <option value="visit_note">Visit Note</option>
                <option value="imaging">Imaging</option>
              </select>
            </div>
            <div className="form-group full-width">
              <label htmlFor="content">Content</label>
              <textarea
                id="content"
                placeholder="Enter the medical record details..."
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                required
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : '✨ Save Record'}
          </button>
        </form>

        <section className="records-section">
          <h3>📚 Medical Records ({records.length})</h3>
          {records.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <p>No medical records yet. Add your first record above!</p>
            </div>
          ) : (
            <div className="records-list">
              {records.map((record) => (
                <div key={record.id} className="record-item">
                  <div className="record-header">
                    <span className="record-title">{record.title}</span>
                    <span className="record-type">{record.record_type}</span>
                  </div>
                  <p className="record-content">{record.content}</p>
                  <div className="record-date">{formatDate(record.created_at)}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
