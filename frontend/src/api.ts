import type { MedicalRecord, CreateRecordPayload } from './types';

const API_BASE = '/api/v1';

export const api = {
  async getHealth(): Promise<{ status: string; service: string }> {
    const res = await fetch('/health');
    return res.json();
  },

  async getRecords(): Promise<MedicalRecord[]> {
    const res = await fetch(`${API_BASE}/records`);
    return res.json();
  },

  async createRecord(payload: CreateRecordPayload): Promise<MedicalRecord> {
    const res = await fetch(`${API_BASE}/records`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async getRecord(id: number): Promise<MedicalRecord> {
    const res = await fetch(`${API_BASE}/records/${id}`);
    return res.json();
  },
};
