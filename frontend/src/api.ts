import type {
  ChatMessage,
  ContextSimpleResponse,
  CreateRecordPayload,
  DocumentItem,
  MedicalRecord,
  MemorySearchResponse,
  PatientSummary,
} from './types';
import {
  ApiError as GeneratedApiError,
  AuthenticationService,
  ChatService,
  ContextEngineService,
  DataIngestionService,
  DocumentsService,
  HealthService,
  InsightsService,
  MedicalRecordsService,
  MemorySearchService,
  OpenAPI,
  PatientsService,
} from './api/generated';

const normalizeApiBase = (base: string) => {
  const trimmed = base.replace(/\/+$/, '');
  if (trimmed.endsWith('/api/v1')) return trimmed;
  if (trimmed.endsWith('/api')) return `${trimmed}/v1`;
  return `${trimmed}/api/v1`;
};

const API_BASE = import.meta.env.VITE_API_BASE
  ? normalizeApiBase(import.meta.env.VITE_API_BASE)
  : '/api/v1';

const API_ORIGIN = import.meta.env.VITE_API_BASE
  ? new URL(normalizeApiBase(import.meta.env.VITE_API_BASE)).origin
  : window.location.origin;

const resolveAuthRecoveryUrls = (path: string) => {
  const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
  const candidates = new Set<string>();

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  candidates.add(`${base}${normalizedPath}`);

  if (base.endsWith('/api/v1')) {
    candidates.add(`${base.replace(/\/api\/v1$/, '')}${normalizedPath}`);
  } else if (base.endsWith('/api')) {
    candidates.add(`${base.replace(/\/api$/, '')}${normalizedPath}`);
  }

  candidates.add(`${API_ORIGIN}${normalizedPath}`);

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      const localApiBase = 'http://localhost:8000/api/v1';
      const localAltBase = 'http://127.0.0.1:8000/api/v1';
      candidates.add(`${localApiBase}${normalizedPath}`);
      candidates.add(`${localAltBase}${normalizedPath}`);
    }
  }
  return Array.from(candidates);
};

const getAccessToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_access_token');
};

const getRefreshToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_refresh_token');
};

const getTokenExpiresAt = () => {
  if (typeof window === 'undefined') return null;
  const val = window.localStorage.getItem('medmemory_token_expires_at');
  return val ? parseInt(val, 10) : null;
};

const hasAccessToken = () => Boolean(getAccessToken());

const getApiKey = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_api_key');
};

let refreshPromise: Promise<string | null> | null = null;

const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  
  if (refreshPromise) return refreshPromise;
  
  refreshPromise = (async () => {
    try {
      const urls = resolveAuthRecoveryUrls('/auth/refresh');
      for (const url of urls) {
        try {
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (res.ok) {
            const data = await res.json();
            window.localStorage.setItem('medmemory_access_token', data.access_token);
            window.localStorage.setItem('medmemory_refresh_token', data.refresh_token);
            window.localStorage.setItem('medmemory_token_expires_at', String(Date.now() + data.expires_in * 1000));
            return data.access_token;
          }
          if (res.status === 401) {
            window.localStorage.removeItem('medmemory_access_token');
            window.localStorage.removeItem('medmemory_refresh_token');
            window.localStorage.removeItem('medmemory_token_expires_at');
            return null;
          }
        } catch {
          continue;
        }
      }
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
};

const isTokenExpiringSoon = () => {
  const expiresAt = getTokenExpiresAt();
  if (!expiresAt) return false;
  return Date.now() > expiresAt - 60000;
};

const getAuthHeaders = async () => {
  let accessToken = getAccessToken();
  const apiKey = getApiKey();

  if (accessToken && isTokenExpiringSoon()) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      accessToken = newToken;
    }
  }

  const authHeaders: Record<string, string> = {};

  if (accessToken) {
    authHeaders['Authorization'] = `Bearer ${accessToken}`;
  } else if (apiKey) {
    authHeaders['X-API-Key'] = apiKey;
  }

  return authHeaders;
};

const withAuthHeaders = async (headers: Record<string, string> = {}) => {
  const authHeaders = await getAuthHeaders();
  return { ...headers, ...authHeaders };
};

OpenAPI.BASE = API_ORIGIN;
OpenAPI.HEADERS = async () => getAuthHeaders();

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const getUserFriendlyMessage = (error: unknown) => {
  const formatApiMessage = (status: number, message: string) => {
    if (status === 401 || status === 403) {
      const normalized = message?.toLowerCase() || '';
      if (message && !normalized.includes('not authenticated')) return message;
      return hasAccessToken()
        ? 'Your session has expired. Please sign in again.'
        : 'Invalid email or password.';
    }
    if (status === 0) {
      return 'Unable to reach the server. Please check your connection or try again.';
    }
    if (status === 404) {
      return 'That item could not be found.';
    }
    if (status === 429) {
      return 'Too many requests. Please wait a moment and try again.';
    }
    if (status >= 500) {
      return 'The server ran into a problem. Please try again shortly.';
    }
    return message;
  };

  if (error instanceof ApiError) {
    return formatApiMessage(error.status, error.message);
  }

  if (error instanceof GeneratedApiError) {
    const message =
      error.body?.error?.message ||
      error.body?.detail ||
      error.message ||
      error.statusText ||
      'Unexpected API error';
    return formatApiMessage(error.status, message);
  }

  if (error instanceof Error) return error.message;
  return 'Unexpected error';
};

const parseJson = async (res: Response) => {
  try {
    return await res.json();
  } catch {
    return null;
  }
};

const request = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  try {
    // Use path as-is (it should already include API_BASE or be an absolute URL)
    const fullUrl = path.startsWith('http') ? path : `${window.location.origin}${path}`;
    console.log(`[API] Making request to: ${fullUrl}`);
    console.log(`[API] Request options:`, { 
      method: options.method || 'GET',
      hasAuth: !!(options.headers as Record<string, string>)?.Authorization,
      headers: Object.keys(options.headers || {})
    });
    
    const res = await fetch(path, options);
    console.log(`[API] Response status: ${res.status} ${res.statusText} for ${fullUrl}`);
    
    const data = await parseJson(res);

    if (!res.ok) {
      const message =
        data?.error?.message ||
        data?.detail ||
        res.statusText ||
        'Unexpected API error';
      console.error(`[API] Request failed: ${res.status} - ${message}`);
      throw new ApiError(res.status, message);
    }

    console.log(`[API] Request successful: ${fullUrl}`);
    return data as T;
  } catch (error) {
    // Re-throw ApiError as-is
    if (error instanceof ApiError) {
      throw error;
    }
    // Handle network errors with more helpful message
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const errorMessage = error.message;
      const fullUrl = path.startsWith('http') ? path : `${window.location.origin}${path}`;
      console.error(`[API] Network error for ${fullUrl}:`, errorMessage);
      console.error(`[API] Current origin: ${window.location.origin}`);
      console.error(`[API] API_BASE: ${API_BASE}`);
      throw new ApiError(0, `Network error: Unable to reach the API server at ${fullUrl}. Please check if the backend is running on port 8000 and the Vite dev server proxy is configured correctly. Error: ${errorMessage}`);
    }
    // Re-throw other errors
    throw error;
  }
};

export const api = {
  async getHealth(): Promise<{ status: string; service: string }> {
    return HealthService.healthCheckHealthGet();
  },

  async signup(email: string, password: string, fullName: string) {
    return AuthenticationService.signupApiV1AuthSignupPost({
      email,
      password,
      full_name: fullName,
    });
  },

  async login(email: string, password: string) {
    return AuthenticationService.loginApiV1AuthLoginPost({ email, password });
  },

  async forgotPassword(email: string): Promise<{ message: string }> {
    const urls = resolveAuthRecoveryUrls('/auth/forgot-password');
    let lastError: unknown;
    for (const url of urls) {
      try {
        return await request(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
      } catch (error) {
        lastError = error;
        if (error instanceof ApiError && error.status === 404) {
          continue;
        }
        throw error;
      }
    }
    throw lastError;
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const urls = resolveAuthRecoveryUrls('/auth/reset-password');
    let lastError: unknown;
    for (const url of urls) {
      try {
        return await request(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, new_password: newPassword }),
        });
      } catch (error) {
        lastError = error;
        if (error instanceof ApiError && error.status === 404) {
          continue;
        }
        throw error;
      }
    }
    throw lastError;
  },

  async getCurrentUser() {
    return AuthenticationService.getCurrentUserInfoApiV1AuthMeGet();
  },

  async logout(): Promise<void> {
    const urls = resolveAuthRecoveryUrls('/auth/logout');
    const headers = await getAuthHeaders();
    for (const url of urls) {
      try {
        await fetch(url, {
          method: 'POST',
          headers,
        });
        return;
      } catch {
        continue;
      }
    }
  },

  async listPatients(search?: string): Promise<PatientSummary[]> {
    return PatientsService.listPatientsApiV1PatientsGet(undefined, 100, search ?? null);
  },

  async getPatient(patientId: number): Promise<PatientSummary> {
    const response = await PatientsService.getPatientApiV1PatientsPatientIdGet(patientId);
    return {
      id: response.id,
      full_name: response.full_name,
      date_of_birth: response.date_of_birth,
      age: response.age,
      gender: response.gender,
    };
  },

  async createPatient(payload: {
    first_name: string;
    last_name: string;
    date_of_birth?: string;
    gender?: string;
    email?: string;
  }): Promise<PatientSummary> {
    const response = await PatientsService.createPatientApiV1PatientsPost(payload);
    // Convert PatientResponse to PatientSummary format
    return {
      id: response.id,
      full_name: response.full_name,
      date_of_birth: response.date_of_birth,
      age: response.age,
      gender: response.gender,
    };
  },

  async getRecords(patientId?: number): Promise<MedicalRecord[]> {
    return MedicalRecordsService.listRecordsApiV1RecordsGet(patientId ?? null);
  },

  async createRecord(patientId: number, payload: CreateRecordPayload): Promise<MedicalRecord> {
    return MedicalRecordsService.createRecordApiV1RecordsPost(patientId, payload);
  },

  async listDocuments(patientId: number): Promise<DocumentItem[]> {
    return DocumentsService.listDocumentsApiV1DocumentsGet(patientId);
  },

  async uploadDocument(
    patientId: number,
    file: File,
    metadata: { title?: string; category?: string; document_type?: string; description?: string } = {},
  ): Promise<DocumentItem> {
    const form = new FormData();
    form.append('file', file);
    form.append('patient_id', String(patientId));
    if (metadata.document_type) form.append('document_type', metadata.document_type);
    if (metadata.title) form.append('title', metadata.title);
    if (metadata.category) form.append('category', metadata.category);
    if (metadata.description) form.append('description', metadata.description);

    return DocumentsService.uploadDocumentApiV1DocumentsUploadPost({
      file,
      patient_id: patientId,
      document_type: metadata.document_type ?? null,
      title: metadata.title ?? null,
      category: metadata.category ?? null,
      description: metadata.description ?? null,
    });
  },

  async processDocument(documentId: number): Promise<{ status: string; chunks_created: number }> {
    return DocumentsService.processDocumentApiV1DocumentsDocumentIdProcessPost(documentId, {
      create_memory_chunks: true,
    });
  },

  async getDocumentText(documentId: number): Promise<{ document_id: number; extracted_text: string; page_count: number }> {
    return DocumentsService.getDocumentTextApiV1DocumentsDocumentIdTextGet(documentId);
  },

  async getDocumentOcr(documentId: number): Promise<{
    document_id: number;
    ocr_language?: string | null;
    ocr_confidence?: number | null;
    ocr_text_raw?: string | null;
    ocr_text_cleaned?: string | null;
    ocr_entities?: Record<string, unknown>;
    used_ocr: boolean;
  }> {
    return DocumentsService.getDocumentOcrApiV1DocumentsDocumentIdOcrGet(documentId);
  },

  async visionChat(
    patientId: number,
    prompt: string,
    image: File,
  ): Promise<{
    answer: string;
    tokens_input: number;
    tokens_generated: number;
    tokens_total: number;
    generation_time_ms: number;
  }> {
    return ChatService.askWithImageApiV1ChatVisionPost({
      prompt,
      patient_id: patientId,
      image,
    });
  },

  async volumeChat(
    patientId: number,
    prompt: string,
    volume: File,
    options?: { sampleCount?: number; tileSize?: number; modality?: string },
  ): Promise<{
    answer: string;
    total_slices: number;
    sampled_indices: number[];
    grid_rows: number;
    grid_cols: number;
    tile_size: number;
    tokens_input: number;
    tokens_generated: number;
    tokens_total: number;
    generation_time_ms: number;
  }> {
    return ChatService.askWithVolumeApiV1ChatVolumePost({
      prompt,
      patient_id: patientId,
      slices: [volume],
      sample_count: options?.sampleCount,
      tile_size: options?.tileSize,
      modality: options?.modality,
    });
  },

  async wsiChat(
    patientId: number,
    prompt: string,
    patches: File,
    options?: { sampleCount?: number; tileSize?: number },
  ): Promise<{
    answer: string;
    total_patches: number;
    sampled_indices: number[];
    grid_rows: number;
    grid_cols: number;
    tile_size: number;
    tokens_input: number;
    tokens_generated: number;
    tokens_total: number;
    generation_time_ms: number;
  }> {
    return ChatService.askWithWsiApiV1ChatWsiPost({
      prompt,
      patient_id: patientId,
      patches: [patches],
      sample_count: options?.sampleCount,
      tile_size: options?.tileSize,
    });
  },

  async compareCxr(
    patientId: number,
    prompt: string,
    currentImage: File,
    priorImage: File,
  ): Promise<{
    answer: string;
    tokens_input: number;
    tokens_generated: number;
    tokens_total: number;
    generation_time_ms: number;
  }> {
    return ChatService.compareCxrApiV1ChatCxrComparePost({
      prompt,
      patient_id: patientId,
      current_image: currentImage,
      prior_image: priorImage,
    });
  },

  async localizeFindings(
    patientId: number,
    prompt: string,
    image: File,
    modality: string,
  ): Promise<{
    answer: string;
    boxes: Array<{
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
    }>;
    image_width: number;
    image_height: number;
    tokens_input: number;
    tokens_generated: number;
    tokens_total: number;
    generation_time_ms: number;
  }> {
    return ChatService.localizeFindingsApiV1ChatLocalizePost({
      prompt,
      patient_id: patientId,
      image,
      modality,
    });
  },

  async getPatientInsights(patientId: number): Promise<{
    patient_id: number;
    lab_total: number;
    lab_abnormal: number;
    recent_labs: Array<{
      test_name: string;
      value?: string | null;
      unit?: string | null;
      collected_at?: string | null;
      is_abnormal: boolean;
    }>;
    active_medications: number;
    recent_medications: Array<{
      name: string;
      dosage?: string | null;
      frequency?: string | null;
      status?: string | null;
      prescribed_at?: string | null;
      start_date?: string | null;
    }>;
    a1c_series: number[];
  }> {
    return InsightsService.getPatientInsightsApiV1InsightsPatientPatientIdGet(patientId);
  },

  async memorySearch(patientId: number, query: string): Promise<MemorySearchResponse> {
    return MemorySearchService.semanticSearchApiV1MemorySearchPost({
      query,
      patient_id: patientId,
      limit: 5,
    });
  },

  async getContext(patientId: number, question: string): Promise<ContextSimpleResponse> {
    return ContextEngineService.getSimpleContextApiV1ContextSimplePost({
      patient_id: patientId,
      query: question,
      max_tokens: 2000,
    });
  },

  async ingestBatch(payload: {
    labs?: unknown[];
    medications?: unknown[];
    encounters?: unknown[];
  }) {
    return DataIngestionService.ingestBatchApiV1IngestBatchPost(payload);
  },

  async chatAsk(patientId: number, question: string): Promise<{ answer: string } & Record<string, unknown>> {
    return ChatService.askQuestionApiV1ChatAskPost({
      question,
      patient_id: patientId,
    });
  },

  async streamChat(
    patientId: number,
    question: string,
    onChunk: (chunk: string) => void,
    onDone: () => void,
  ) {
    const headers = await withAuthHeaders();
    const res = await fetch(
      `${API_BASE}/chat/stream?patient_id=${patientId}&question=${encodeURIComponent(question)}`,
      {
        method: 'POST',
        headers,
      },
    );

    if (!res.ok) {
      const data = await parseJson(res);
      const message = data?.error?.message || data?.detail || res.statusText;
      throw new ApiError(res.status, message);
    }

    if (!res.body) {
      onDone();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.replace('data:', '').trim();
        if (!jsonStr) continue;
        try {
          const payload = JSON.parse(jsonStr) as { chunk?: string; is_complete?: boolean };
          if (payload.chunk) {
            onChunk(payload.chunk);
          }
          if (payload.is_complete) {
            onDone();
          }
        } catch {
          continue;
        }
      }
    }
  },
};

export const seedChatMessages = (messages: ChatMessage[], next: ChatMessage) => {
  return [...messages, next];
};
