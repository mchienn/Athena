import type { ApiErrorShape } from '../types';

const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';
const useMocks = !baseUrl;

export class ApiError extends Error implements ApiErrorShape {
  constructor(public status: number, public code: string, message: string) { super(message); this.name = 'ApiError'; }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!baseUrl) throw new ApiError(0, 'MOCK_MODE', 'API chưa được cấu hình');
  try {
    const headers = new Headers(options.headers);
    headers.set('Content-Type', 'application/json');
    headers.set('Accept', 'application/json');
    const token = localStorage.getItem('auth_token');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { message?: string; detail?: string; code?: string };
      throw new ApiError(response.status, body.code ?? 'API_ERROR', body.message ?? body.detail ?? 'Không thể xử lý yêu cầu');
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'NETWORK_ERROR', 'Mất kết nối. Vui lòng kiểm tra mạng và thử lại.');
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T, B = unknown>(path: string, body: B) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T, B = unknown>(path: string, body: B) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T, B = unknown>(path: string, body: B) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  useMocks,
};

export const mockDelay = async <T>(value: T, delay = 250): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(value), delay));
