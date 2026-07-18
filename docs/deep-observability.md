# Athena deep observability design

## Outcome

The production stack uses Google Cloud's native observability path:

1. Cloud Run emits request logs and privacy-safe JSON application events.
2. Cloud Logging converts selected events into bounded-cardinality metrics.
3. Cloud Monitoring visualizes those metrics and alerts the operations email.
4. Google ADK exports invocation, agent and tool relationships to Cloud Trace.
5. The browser reports sanitized runtime errors and Core Web Vitals through the
   same-origin auth API.

No third-party monitoring service or client-side GCP credential is required.

## Privacy boundary

Telemetry may contain service, operation, route template, status class,
duration, agent/model/tool name, token counts, Web Vital values, browser error
class and a one-way error fingerprint.

Telemetry must not contain prompts, responses, request bodies, query strings,
headers, tokens, IP addresses, phone numbers, patient/user identifiers, names,
medical records, tool arguments or tool responses. ADK content capture remains
set to `NO_CONTENT`.

## Signals

- Agent: model calls, success/failure, input/output token distribution, model
  latency, tool calls and tool latency.
- Product: register, login, refresh, logout and create-appointment outcomes and
  latency.
- Frontend: React errors, uncaught errors, unhandled promises, LCP, INP, CLS,
  FCP and TTFB.
- Platform: request rate, 5xx ratio, request latency, instances, CPU, memory,
  uptime and revision health.

The browser sends no raw message or stack. It hashes the local error
name/message/top frame and sends only the error class and fingerprint. Dynamic
route identifiers are replaced with `:id`.

The public browser-ingestion endpoint also applies a per-instance limit of 300
accepted events per minute to bound accidental loops and basic telemetry spam.

## Provisioning

All custom resources are versioned under `deploy/observability`. Reapply them:

```powershell
./deploy/observability/apply-observability.ps1
```

The script upserts 12 log-based metrics, seven alert policies and the `Athena
Agent and Product Observability` dashboard. Labels intentionally exclude
fingerprints, release IDs and user-controlled values where they would create
unbounded time-series cardinality.

Log-based metrics are billable Cloud Monitoring custom metrics beyond the
applicable Google Cloud allotment. Keep retention, metric labels and alert
thresholds under review as production traffic grows.

## First response

1. Start with the deep dashboard and identify model, tool, product or frontend.
2. For an agent failure, query `jsonPayload.telemetry_type="agent"`, copy the
   linked trace ID, then inspect the invocation in Cloud Trace.
3. For a frontend fingerprint, group matching logs by route, release and error
   class. Reproduce with that release; raw browser content is intentionally not
   available.
4. For a booking/auth failure, compare the business event with the matching
   Cloud Run request log and revision.
