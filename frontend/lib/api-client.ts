/**
 * API client for InvestFlow backend
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

export interface ApiError {
  detail: string;
}

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_URL}${API_PREFIX}`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const startTime = performance.now();
    
    console.log(`[API] 🚀 ${options.method || 'GET'} ${endpoint}`);
    
    // Get token from localStorage
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const fetchStart = performance.now();
    const response = await fetch(url, {
      ...options,
      headers,
    });
    const fetchTime = performance.now() - fetchStart;

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const error: ApiError = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // JSON parsing failed, use default error message
      }
      const totalTime = performance.now() - startTime;
      console.error(`[API] ❌ ${options.method || 'GET'} ${endpoint} - ${response.status} in ${totalTime.toFixed(0)}ms`, { url, status: response.status });
      throw new Error(errorDetail);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      const totalTime = performance.now() - startTime;
      console.log(`[API] ✅ ${options.method || 'GET'} ${endpoint} - 204 No Content in ${totalTime.toFixed(0)}ms`);
      return null as T;
    }

    const jsonStart = performance.now();
    const data = await response.json();
    const jsonTime = performance.now() - jsonStart;
    const totalTime = performance.now() - startTime;
    
    console.log(`[API] ✅ ${options.method || 'GET'} ${endpoint} - ${response.status} in ${totalTime.toFixed(0)}ms (fetch: ${fetchTime.toFixed(0)}ms, json: ${jsonTime.toFixed(0)}ms)`);
    
    return data;
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async upload<T>(
    endpoint: string,
    formData: FormData
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  }
}

export const apiClient = new ApiClient();

