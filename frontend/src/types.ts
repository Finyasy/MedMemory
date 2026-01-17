export interface MedicalRecord {
  id: number;
  patient_id: number;
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

export interface DocumentItem {
  id: number;
  patient_id: number;
  document_type: string;
  title?: string | null;
  original_filename: string;
  processing_status: string;
  is_processed: boolean;
  page_count?: number | null;
}

export interface MemorySearchResult {
  chunk_id: number;
  content: string;
  source_type: string;
  source_id?: number | null;
  similarity_score: number;
  context_date?: string | null;
}

export interface MemorySearchResponse {
  results: MemorySearchResult[];
  total_results: number;
}

export interface ContextSimpleResponse {
  context: string;
  prompt: string;
  num_sources: number;
  estimated_tokens: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface PatientSummary {
  id: number;
  full_name: string;
  date_of_birth?: string | null;
  age?: number | null;
  gender?: string | null;
}
