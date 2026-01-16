export interface MedicalRecord {
  id: number;
  title: string;
  content: string;
  record_type: string;
  created_at: string;
}

export interface CreateRecordPayload {
  title: string;
  content: string;
  record_type?: string;
}
