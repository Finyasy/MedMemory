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

export interface ChatSource {
  source_type: string;
  source_id?: number | null;
  relevance: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  num_sources?: number;
  sources?: ChatSource[];
  structured_data?: Record<string, unknown> | null;
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

export interface DataConnection {
  id: number;
  patient_id: number;
  provider_name: string;
  provider_slug: string;
  status: 'connected' | 'syncing' | 'error' | 'disconnected';
  source_count: number;
  last_error?: string | null;
  last_synced_at?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DataConnectionUpsertPayload {
  provider_name: string;
  provider_slug: string;
  status?: 'connected' | 'syncing' | 'error' | 'disconnected';
  source_count?: number;
  last_error?: string | null;
  last_synced_at?: string | null;
  is_active?: boolean;
}

export interface DashboardSummary {
  out_of_range: number;
  in_range: number;
  tracked_metrics: number;
  last_updated_at?: string | null;
}

export interface HighlightItem {
  metric_key: string;
  metric_name: string;
  value?: string | null;
  numeric_value?: number | null;
  unit?: string | null;
  observed_at?: string | null;
  status: 'out_of_range' | 'in_range';
  direction?: string | null;
  trend_delta?: number | null;
  reference_range?: string | null;
  risk_priority_score?: number;
  risk_priority_reason?: string | null;
  source_type: string;
  source_id?: number | null;
  provider_name?: string | null;
  confidence_score?: number | null;
  confidence_label?: 'high' | 'medium' | 'low' | string | null;
  freshness_days?: number | null;
}

export interface DashboardHighlightsResponse {
  patient_id: number;
  summary: DashboardSummary;
  highlights: HighlightItem[];
}

export interface MetricTrendPoint {
  value?: number | null;
  value_text?: string | null;
  raw_value?: number | null;
  raw_value_text?: string | null;
  raw_unit?: string | null;
  normalized_value?: number | null;
  normalized_value_text?: string | null;
  normalized_unit?: string | null;
  observed_at?: string | null;
  source_type?: string | null;
  source_id?: number | null;
  provider_name?: string | null;
  confidence_score?: number | null;
  confidence_label?: 'high' | 'medium' | 'low' | string | null;
  freshness_days?: number | null;
  excluded_from_insights?: boolean;
  exclusion_reason?: string | null;
}

export interface MetricDetail {
  patient_id: number;
  metric_key: string;
  metric_name: string;
  latest_value?: string | null;
  latest_numeric_value?: number | null;
  unit?: string | null;
  observed_at?: string | null;
  reference_range?: string | null;
  range_min?: number | null;
  range_max?: number | null;
  in_range?: boolean | null;
  about: string;
  latest_source_type?: string | null;
  latest_source_id?: number | null;
  normalized_unit?: string | null;
  latest_normalized_value?: number | null;
  latest_normalized_value_text?: string | null;
  normalization_applied?: boolean;
  latest_confidence_score?: number | null;
  latest_confidence_label?: 'high' | 'medium' | 'low' | string | null;
  latest_freshness_days?: number | null;
  excluded_points_count?: number;
  trend: MetricTrendPoint[];
}

export interface WatchMetric {
  id: number;
  patient_id: number;
  metric_name: string;
  metric_key: string;
  lower_bound?: number | null;
  upper_bound?: number | null;
  direction: 'above' | 'below' | 'both';
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WatchMetricPayload {
  metric_name: string;
  metric_key: string;
  lower_bound?: number | null;
  upper_bound?: number | null;
  direction?: 'above' | 'below' | 'both';
  is_active?: boolean;
}

export interface MetricAlert {
  id: number;
  patient_id: number;
  watch_metric_id?: number | null;
  metric_key: string;
  metric_name: string;
  numeric_value?: number | null;
  value_text?: string | null;
  previous_numeric_value?: number | null;
  previous_value_text?: string | null;
  unit?: string | null;
  trend_delta?: number | null;
  alert_kind: 'threshold' | 'abnormal' | 'trend_change';
  severity: 'info' | 'warning' | 'critical';
  reason: string;
  source_type: string;
  source_id?: number | null;
  observed_at?: string | null;
  previous_observed_at?: string | null;
  acknowledged: boolean;
  acknowledged_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionSyncEvent {
  id: number;
  patient_id: number;
  connection_id?: number | null;
  provider_slug: string;
  event_type: string;
  status_before?: string | null;
  status_after?: string | null;
  details?: string | null;
  last_error?: string | null;
  triggered_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface AlertsEvaluateResponse {
  generated: number;
  total_active_unacknowledged: number;
}

export interface ClinicianAccessRequest {
  grant_id: number;
  patient_id: number;
  patient_name: string;
  clinician_user_id: number;
  clinician_name: string;
  clinician_email: string;
  status: string;
  scopes: string;
  created_at: string;
}
