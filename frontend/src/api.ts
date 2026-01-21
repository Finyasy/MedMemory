import type {
  ChatMessage,
  ContextSimpleResponse,
  CreateRecordPayload,
  DocumentItem,
  MedicalRecord,
  MemorySearchResponse,
  PatientSummary,
} from './types';

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

const getAccessToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_access_token');
};

const hasAccessToken = () => Boolean(getAccessToken());

const getApiKey = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_api_key');
};

const withAuthHeaders = (headers: Record<string, string> = {}) => {
  const accessToken = getAccessToken();
  const apiKey = getApiKey();
  
  const authHeaders: Record<string, string> = { ...headers };
  
  // Prefer JWT token over API key
  if (accessToken) {
    authHeaders['Authorization'] = `Bearer ${accessToken}`;
    console.log('[API] Using JWT token for authentication');
  } else if (apiKey) {
    authHeaders['X-API-Key'] = apiKey;
    console.log('[API] Using API key for authentication');
  } else {
    console.warn('[API] No authentication token found');
  }
  
  return authHeaders;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const getUserFriendlyMessage = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      if (error.message) return error.message;
      return hasAccessToken()
        ? 'Your session has expired. Please sign in again.'
        : 'Invalid email or password.';
    }
    if (error.status === 0) {
      return 'Unable to reach the server. Please check your connection or try again.';
    }
    if (error.status === 404) {
      return 'That item could not be found.';
    }
    if (error.status === 429) {
      return 'Too many requests. Please wait a moment and try again.';
    }
    if (error.status >= 500) {
      return 'The server ran into a problem. Please try again shortly.';
    }
    return error.message;
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
    return request(`${API_ORIGIN}/health`);
  },

  async signup(email: string, password: string, fullName: string) {
    return request<{
      access_token: string;
      token_type: string;
      user_id: number;
      email: string;
    }>(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  },

  async login(email: string, password: string) {
    return request<{
      access_token: string;
      token_type: string;
      user_id: number;
      email: string;
    }>(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  },

  async getCurrentUser() {
    return request<{
      id: number;
      email: string;
      full_name: string;
      is_active: boolean;
    }>(`${API_BASE}/auth/me`, {
      headers: withAuthHeaders(),
    });
  },

  async listPatients(search?: string): Promise<PatientSummary[]> {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    const query = params.toString();
    const url = query ? `${API_BASE}/patients/?${query}` : `${API_BASE}/patients/`;
    return request(url, {
      headers: withAuthHeaders(),
    });
  },

  async getPatient(patientId: number): Promise<PatientSummary> {
    const response = await request<{
      id: number;
      full_name: string;
      date_of_birth?: string | null;
      age?: number | null;
      gender?: string | null;
    }>(`${API_BASE}/patients/${patientId}`, {
      headers: withAuthHeaders(),
    });
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
    const response = await request<{
      id: number;
      full_name: string;
      date_of_birth?: string | null;
      age?: number | null;
      gender?: string | null;
    }>(`${API_BASE}/patients/`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
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
    const query = patientId ? `?patient_id=${patientId}` : '';
    return request(`${API_BASE}/records/${query}`, {
      headers: withAuthHeaders(),
    });
  },

  async createRecord(patientId: number, payload: CreateRecordPayload): Promise<MedicalRecord> {
    return request(`${API_BASE}/records/?patient_id=${patientId}`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
  },

  async listDocuments(patientId: number): Promise<DocumentItem[]> {
    return request(`${API_BASE}/documents/patient/${patientId}`, {
      headers: withAuthHeaders(),
    });
  },

  async uploadDocument(
    patientId: number,
    file: File,
    metadata: { title?: string; category?: string; document_type?: string } = {},
  ): Promise<DocumentItem> {
    const form = new FormData();
    form.append('file', file);
    form.append('patient_id', String(patientId));
    if (metadata.document_type) form.append('document_type', metadata.document_type);
    if (metadata.title) form.append('title', metadata.title);
    if (metadata.category) form.append('category', metadata.category);

    return request(`${API_BASE}/documents/upload`, {
      method: 'POST',
      headers: withAuthHeaders(),
      body: form,
    });
  },

  async processDocument(documentId: number): Promise<{ status: string; chunks_created: number }> {
    return request(`${API_BASE}/documents/${documentId}/process`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ create_memory_chunks: true }),
    });
  },

  async getDocumentText(documentId: number): Promise<{ document_id: number; extracted_text: string; page_count: number }> {
    return request(`${API_BASE}/documents/${documentId}/text`, {
      headers: withAuthHeaders(),
    });
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
    return request(`${API_BASE}/documents/${documentId}/ocr`, {
      headers: withAuthHeaders(),
    });
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
    const form = new FormData();
    form.append('prompt', prompt);
    form.append('patient_id', String(patientId));
    form.append('image', image);

    return request(`${API_BASE}/chat/vision`, {
      method: 'POST',
      headers: withAuthHeaders(),
      body: form,
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
    return request(`${API_BASE}/insights/patient/${patientId}`, {
      headers: withAuthHeaders(),
    });
  },

  async memorySearch(patientId: number, query: string): Promise<MemorySearchResponse> {
    return request(`${API_BASE}/memory/search`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query, patient_id: patientId, limit: 5 }),
    });
  },

  async getContext(patientId: number, question: string): Promise<ContextSimpleResponse> {
    return request(`${API_BASE}/context/simple`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ patient_id: patientId, query: question, max_tokens: 2000 }),
    });
  },

  async ingestBatch(payload: {
    labs?: unknown[];
    medications?: unknown[];
    encounters?: unknown[];
  }) {
    return request(`${API_BASE}/ingest/batch`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
  },

  async chatAsk(patientId: number, question: string): Promise<{ answer: string } & Record<string, unknown>> {
    return request(`${API_BASE}/chat/ask`, {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ question, patient_id: patientId }),
    });
  },

  async streamChat(
    patientId: number,
    question: string,
    onChunk: (chunk: string) => void,
    onDone: () => void,
  ) {
    const res = await fetch(
      `${API_BASE}/chat/stream?patient_id=${patientId}&question=${encodeURIComponent(question)}`,
      {
        method: 'POST',
        headers: withAuthHeaders(),
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
