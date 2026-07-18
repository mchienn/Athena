import { ApiError } from './apiClient';

const bookingBaseUrl = (
  import.meta.env.VITE_BOOKING_API_BASE_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  '/booking-api/api'
).replace(/\/$/, '');

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  const token = localStorage.getItem('auth_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  try {
    const response = await fetch(`${bookingBaseUrl}${path}`, { ...options, headers });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as {
        detail?: string;
        message?: string;
        code?: string;
      };
      throw new ApiError(
        response.status,
        body.code ?? 'BOOKING_API_ERROR',
        body.detail ?? body.message ?? 'Không thể xử lý yêu cầu đặt lịch',
      );
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      'BOOKING_NETWORK_ERROR',
      'Không thể kết nối dịch vụ lịch khám. Vui lòng thử lại.',
    );
  }
}

export const bookingApiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T, B>(path: string, body: B) => request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  }),
};
