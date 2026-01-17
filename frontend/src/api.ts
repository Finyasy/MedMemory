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

const getAccessToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('medmemory_access_token');
};

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
  } else if (apiKey) {
    authHeaders['X-API-Key'] = apiKey;
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
      return 'Your session has expired. Please sign in again.';
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
  const res = await fetch(path, options);
  const data = await parseJson(res);

  if (!res.ok) {
    const message =
      data?.error?.message ||
      data?.detail ||
      res.statusText ||
      'Unexpected API error';
    throw new ApiError(res.status, message);
  }

  return data as T;
};

export const api = {
  async getHealth(): Promise<{ status: string; service: string }> {
    return request('/health');
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
    return request(`${API_BASE}/patients${query ? `?${query}` : ''}`, {
      headers: withAuthHeaders(),
    });
  },

  async getRecords(patientId?: number): Promise<MedicalRecord[]> {
    const query = patientId ? `?patient_id=${patientId}` : '';
    return request(`${API_BASE}/records${query}`, {
      headers: withAuthHeaders(),
    });
  },

  async createRecord(patientId: number, payload: CreateRecordPayload): Promise<MedicalRecord> {
    return request(`${API_BASE}/records?patient_id=${patientId}`, {
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
