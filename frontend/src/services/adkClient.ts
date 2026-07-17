import type { AssistantMessage } from '../types';

interface AdkPart {
  text?: string;
}

interface AdkEvent {
  content?: {
    role?: string;
    parts?: AdkPart[];
  };
  errorCode?: string;
  errorMessage?: string;
}

const baseUrl = (import.meta.env.VITE_ADK_API_BASE_URL || 'http://127.0.0.1:8000').replace(
  /\/$/,
  '',
);
const appName = import.meta.env.VITE_ADK_APP_NAME || 'hanoi_heart_assistant';

export class AdkApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'AdkApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new AdkApiError(
      'Không thể kết nối ADK API Server. Hãy kiểm tra server và cấu hình CORS.',
      0,
    );
  }

  if (!response.ok) {
    const body = await response.text();
    throw new AdkApiError(body || `ADK API trả về lỗi ${response.status}.`, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function sessionPath(userId: string, sessionId: string): string {
  return `/apps/${encodeURIComponent(appName)}/users/${encodeURIComponent(
    userId,
  )}/sessions/${encodeURIComponent(sessionId)}`;
}

function getFinalAnswer(events: AdkEvent[]): string {
  const errorEvent = [...events].reverse().find((event) => event.errorMessage);
  if (errorEvent?.errorMessage) {
    throw new AdkApiError(errorEvent.errorMessage, 500);
  }

  const modelEvent = [...events]
    .reverse()
    .find((event) => event.content?.role === 'model' && event.content.parts?.some((part) => part.text));
  const answer = modelEvent?.content?.parts
    ?.map((part) => part.text || '')
    .join('')
    .trim();

  if (!answer) {
    throw new AdkApiError('Trợ lý chưa trả về nội dung. Vui lòng thử lại.', 502);
  }

  return answer;
}

export const adkClient = {
  ensureSession: async (userId: string, sessionId: string): Promise<void> => {
    const path = sessionPath(userId, sessionId);
    try {
      await request<unknown>(path);
    } catch (error) {
      if (!(error instanceof AdkApiError) || error.status !== 404) throw error;
      try {
        await request<unknown>(path, { method: 'POST', body: JSON.stringify({}) });
      } catch (creationError) {
        if (!(creationError instanceof AdkApiError) || creationError.status !== 409) {
          throw creationError;
        }
      }
    }
  },

  sendMessage: async (
    userId: string,
    sessionId: string,
    text: string,
  ): Promise<AssistantMessage> => {
    await adkClient.ensureSession(userId, sessionId);
    const events = await request<AdkEvent[]>('/run', {
      method: 'POST',
      body: JSON.stringify({
        appName,
        userId,
        sessionId,
        newMessage: { role: 'user', parts: [{ text }] },
      }),
    });

    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      intent: 'general',
      answer: getFinalAnswer(events),
      actions: [],
      structured_data: {},
      emergency: false,
      citations: [],
    };
  },
};
