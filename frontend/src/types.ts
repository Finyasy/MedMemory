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
  description?: string | null;
  processing_status: string;
  is_processed: boolean;
  page_count?: number | null;
}

export interface DocumentOcrRefinement {
  document_id: number;
  ocr_language?: string | null;
  ocr_confidence?: number | null;
  ocr_text_raw?: string | null;
  ocr_text_cleaned?: string | null;
  ocr_entities?: Record<string, unknown>;
  used_ocr: boolean;
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

export interface LocalizationBox {
  label: string;
  confidence: number;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  x_min_norm: number;
  y_min_norm: number;
  x_max_norm: number;
  y_max_norm: number;
}

export interface LocalizationResult {
  answer: string;
  boxes: LocalizationBox[];
  image_width: number;
  image_height: number;
}

export interface PatientSummary {
  id: number;
  full_name: string;
  date_of_birth?: string | null;
  age?: number | null;
  gender?: string | null;
}
