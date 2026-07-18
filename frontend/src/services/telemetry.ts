import { onCLS, onFCP, onINP, onLCP, onTTFB, type Metric } from 'web-vitals';

type ErrorSource = 'window_error' | 'unhandled_rejection' | 'react_error';

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const endpoint = `${apiBaseUrl}/telemetry/frontend`;
const release = import.meta.env.VITE_RELEASE || undefined;
const recentlySent = new Map<string, number>();
let initialized = false;

function sanitizedRoute(): string {
  return window.location.pathname
    .split('/')
    .map((segment) => (
      /^\d+$/.test(segment)
      || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(segment)
      || /^[A-Za-z0-9_-]{24,}$/.test(segment)
        ? ':id'
        : segment
    ))
    .join('/') || '/';
}

function send(payload: Record<string, unknown>): void {
  const body = JSON.stringify({ ...payload, route: sanitizedRoute(), release });
  if (navigator.sendBeacon) {
    const accepted = navigator.sendBeacon(
      endpoint,
      new Blob([body], { type: 'application/json' }),
    );
    if (accepted) return;
  }
  void fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    credentials: 'include',
    keepalive: true,
  }).catch(() => undefined);
}

async function sha256(value: string): Promise<string> {
  if (!window.crypto?.subtle) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return Math.abs(hash >>> 0).toString(16).padStart(16, '0');
  }
  const digest = await window.crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}

function normalizedError(error: unknown): { name: string; fingerprintSource: string } {
  if (error instanceof Error) {
    const topFrame = error.stack?.split('\n').slice(0, 2).join('|') || '';
    return {
      name: error.name.slice(0, 64) || 'Error',
      fingerprintSource: `${error.name}|${error.message}|${topFrame}`,
    };
  }
  return { name: 'UnknownError', fingerprintSource: typeof error };
}

export async function reportFrontendError(error: unknown, source: ErrorSource): Promise<void> {
  const normalized = normalizedError(error);
  const fingerprint = await sha256(normalized.fingerprintSource);
  const now = Date.now();
  const lastSent = recentlySent.get(fingerprint) || 0;
  if (now - lastSent < 30_000) return;
  recentlySent.set(fingerprint, now);
  send({
    kind: 'error',
    source,
    error_name: normalized.name,
    fingerprint,
  });
}

function reportWebVital(metric: Metric): void {
  send({
    kind: 'web_vital',
    metric_name: metric.name,
    metric_value: metric.value,
    rating: metric.rating,
    navigation_type: metric.navigationType,
  });
}

export function initializeFrontendTelemetry(): void {
  if (initialized) return;
  initialized = true;

  window.addEventListener('error', (event) => {
    void reportFrontendError(event.error || new Error(event.type), 'window_error');
  });
  window.addEventListener('unhandledrejection', (event) => {
    void reportFrontendError(event.reason, 'unhandled_rejection');
  });

  onCLS(reportWebVital);
  onFCP(reportWebVital);
  onINP(reportWebVital);
  onLCP(reportWebVital);
  onTTFB(reportWebVital);
}
