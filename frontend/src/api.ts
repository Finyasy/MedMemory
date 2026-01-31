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
import type {
  BatchIngestionRequest,
  CxrCompareResponse,
  ChatRequest,
  DocumentDetail,
  DocumentProcessResponse,
  LocalizationResponse,
  OcrRefinementResponse,
  PatientInsightsResponse,
  RecordResponse,
  VisionChatResponse,
  VolumeChatResponse,
  WsiChatResponse,
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
    const records = await MedicalRecordsService.listRecordsApiV1RecordsGet(patientId ?? null);
    return records.map((r: RecordResponse) => ({
      ...r,
      record_type: r.record_type ?? 'general',
      created_at: r.created_at ?? new Date().toISOString(),
    }));
  },

  async createRecord(patientId: number, payload: CreateRecordPayload): Promise<MedicalRecord> {
    const r = await MedicalRecordsService.createRecordApiV1RecordsPost(patientId, payload);
    return {
      ...r,
      record_type: r.record_type ?? 'general',
      created_at: r.created_at ?? new Date().toISOString(),
    };
  },

  async listDocuments(patientId: number): Promise<DocumentItem[]> {
    return DocumentsService.listDocumentsApiV1DocumentsGet(patientId);
  },

  async getDocument(documentId: number): Promise<DocumentDetail> {
    return DocumentsService.getDocumentApiV1DocumentsDocumentIdGet(documentId);
  },

  async deleteDocument(documentId: number): Promise<void> {
    return DocumentsService.deleteDocumentApiV1DocumentsDocumentIdDelete(documentId);
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

  async processDocument(documentId: number): Promise<DocumentProcessResponse> {
    return DocumentsService.processDocumentApiV1DocumentsDocumentIdProcessPost(documentId, {
      create_memory_chunks: true,
    });
  },

  async getDocumentText(documentId: number): Promise<{ document_id: number; extracted_text: string; page_count: number }> {
    return DocumentsService.getDocumentTextApiV1DocumentsDocumentIdTextGet(documentId);
  },

  async getDocumentOcr(documentId: number): Promise<OcrRefinementResponse> {
    return DocumentsService.getDocumentOcrApiV1DocumentsDocumentIdOcrGet(documentId);
  },

  async getDocumentStatus(documentId: number): Promise<{
    document_id: number;
    patient_id: number;
    processing_status: string;
    is_processed: boolean;
    processed_at: string | null;
    processing_error: string | null;
    extracted_text_length: number;
    extracted_text_preview: string | null;
    chunks: { total: number; indexed: number; not_indexed: number };
    ocr_confidence: number | null;
    ocr_language: string | null;
    page_count: number | null;
  }> {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const response = await request(`${base}/documents/${documentId}/status`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
    return response as any;
  },

  async checkOcrAvailability(): Promise<{ available: boolean; message: string }> {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const response = await request(`${base}/documents/health/ocr`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
    return response as any;
  },

  async visionChat(
    patientId: number,
    prompt: string,
    image: File,
  ): Promise<VisionChatResponse> {
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
  ): Promise<VolumeChatResponse> {
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
  ): Promise<WsiChatResponse> {
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
  ): Promise<CxrCompareResponse> {
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
  ): Promise<LocalizationResponse> {
    return ChatService.localizeFindingsApiV1ChatLocalizePost({
      prompt,
      patient_id: patientId,
      image,
      modality,
    });
  },

  async getPatientInsights(patientId: number): Promise<PatientInsightsResponse> {
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

  async ingestBatch(payload: BatchIngestionRequest) {
    return DataIngestionService.ingestBatchApiV1IngestBatchPost(payload);
  },

  async chatAsk(
    patientId: number,
    question: string,
    options?: Partial<ChatRequest>,
  ): Promise<{ answer: string } & Record<string, unknown>> {
    return ChatService.askQuestionApiV1ChatAskPost({
      question,
      patient_id: patientId,
      ...options,
    });
  },

  async streamChat(
    patientId: number,
    question: string,
    onChunk: (chunk: string) => void,
    onDone: () => void,
    options?: { clinicianMode?: boolean },
  ) {
    const headers = await withAuthHeaders();
    const params = new URLSearchParams({
      patient_id: String(patientId),
      question,
    });
    if (options?.clinicianMode) params.set('clinician_mode', 'true');
    const res = await fetch(
      `${API_BASE}/chat/stream?${params.toString()}`,
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

  async getAuthHeaders(): Promise<Record<string, string>> {
    return getAuthHeaders();
  },

  // ----- Clinician API -----
  async clinicianSignup(payload: {
    email: string;
    password: string;
    full_name: string;
    registration_number: string;
    specialty?: string;
    organization_name?: string;
    phone?: string;
    address?: string;
  }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user_id: number;
      email: string;
    }>(`${base}/clinician/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  async clinicianLogin(email: string, password: string) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user_id: number;
      email: string;
    }>(`${base}/clinician/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  },

  async getClinicianProfile() {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{
      user_id: number;
      email: string;
      full_name: string;
      npi?: string | null;
      license_number?: string | null;
      specialty?: string | null;
      organization_name?: string | null;
      phone?: string | null;
      address?: string | null;
      verified_at?: string | null;
      created_at?: string | null;
      updated_at?: string | null;
    }>(`${base}/clinician/profile`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },

  async updateClinicianProfile(payload: {
    full_name?: string;
    npi?: string;
    license_number?: string;
    specialty?: string;
    organization_name?: string;
    phone?: string;
    address?: string;
  }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<Parameters<typeof api.getClinicianProfile>[0]>(`${base}/clinician/profile`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
      body: JSON.stringify(payload),
    });
  },

  async listClinicianPatients(statusFilter?: string) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const q = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return request<Array<{
      patient_id: number;
      patient_first_name: string;
      patient_last_name: string;
      patient_full_name: string;
      grant_id: number;
      grant_status: string;
      grant_scopes: string;
      granted_at?: string | null;
      expires_at?: string | null;
    }>>(`${base}/clinician/patients${q}`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },

  async requestPatientAccess(payload: { patient_id: number; scopes?: string; expires_in_days?: number }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{ id: number; patient_id: number; status: string; scopes: string }>(`${base}/clinician/access/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
      body: JSON.stringify(payload),
    });
  },

  async listClinicianUploads(params?: { patient_id?: number; status_filter?: string; skip?: number; limit?: number }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const sp = new URLSearchParams();
    if (params?.patient_id != null) sp.set('patient_id', String(params.patient_id));
    if (params?.status_filter) sp.set('status_filter', params.status_filter);
    if (params?.skip != null) sp.set('skip', String(params.skip));
    if (params?.limit != null) sp.set('limit', String(params.limit));
    const q = sp.toString() ? `?${sp.toString()}` : '';
    return request<DocumentItem[]>(`${base}/clinician/uploads${q}`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },

  async listClinicianPatientDocuments(
    patientId: number,
    params?: { document_type?: string; processed_only?: boolean; skip?: number; limit?: number },
  ) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const sp = new URLSearchParams();
    if (params?.document_type) sp.set('document_type', params.document_type);
    if (params?.processed_only) sp.set('processed_only', 'true');
    if (params?.skip != null) sp.set('skip', String(params.skip));
    if (params?.limit != null) sp.set('limit', String(params.limit));
    const q = sp.toString() ? `?${sp.toString()}` : '';
    return request<DocumentItem[]>(`${base}/clinician/patient/${patientId}/documents${q}`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },

  async listClinicianPatientRecords(patientId: number, params?: { record_type?: string; skip?: number; limit?: number }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const sp = new URLSearchParams();
    if (params?.record_type) sp.set('record_type', params.record_type);
    if (params?.skip != null) sp.set('skip', String(params.skip));
    if (params?.limit != null) sp.set('limit', String(params.limit));
    const q = sp.toString() ? `?${sp.toString()}` : '';
    return request<MedicalRecord[]>(`${base}/clinician/patient/${patientId}/records${q}`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },

  async patientAccessGrant(payload: { grant_id: number; scopes?: string; expires_in_days?: number }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{ id: number; status: string }>(`${base}/patient/access/grant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
      body: JSON.stringify(payload),
    });
  },

  async patientAccessRevoke(payload: { grant_id: number }) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    return request<{ id: number; status: string }>(`${base}/patient/access/revoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
      body: JSON.stringify(payload),
    });
  },

  async listPatientAccessRequests(statusFilter?: string) {
    const base = API_BASE.startsWith('http') ? API_BASE : `${API_ORIGIN}${API_BASE}`;
    const q = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return request<Array<{
      grant_id: number;
      patient_id: number;
      patient_name: string;
      clinician_user_id: number;
      clinician_name: string;
      clinician_email: string;
      status: string;
      scopes: string;
      created_at: string;
    }>>(`${base}/patient/access/requests${q}`, {
      method: 'GET',
      headers: await getAuthHeaders(),
    });
  },
};

export const seedChatMessages = (messages: ChatMessage[], next: ChatMessage) => {
  return [...messages, next];
};
