# GCP operations and monitoring

Project: `project-5d300c02-d165-4037-b6f`

## Automated retention

Artifact Registry repository `athena` uses
`deploy/artifact-cleanup-policy.json`:

- delete image versions older than 30 days;
- always keep the 10 most recent `athena-app` versions;
- run as an active cleanup policy, not a dry run.

Reapply the policy after editing it:

```powershell
gcloud artifacts repositories set-cleanup-policies athena `
  --project=project-5d300c02-d165-4037-b6f `
  --location=asia-southeast1 `
  --policy=deploy/artifact-cleanup-policy.json `
  --no-dry-run
```

Cloud Run keeps inactive revisions for rollback. Inactive revisions receive no
traffic and, with `min-instances=0`, don't run instances. Firebase Hosting's
live channel is configured to retain 10 releases for rollback.

## Monitoring resources

Cloud Monitoring contains four public uptime checks, each running every minute
from Asia Pacific, Europe, and Oregon:

- production frontend `/`;
- ADK `/adk-api/health`;
- booking `/booking-api/health`;
- auth service `/`.

Four alert policies are enabled:

- `Athena production endpoint unavailable`: opens when at least two probe
  regions fail for three minutes;
- `Athena Cloud Run elevated 5xx ratio`: opens when one service returns more
  than 10% HTTP 5xx responses for five minutes.
- `Athena Cloud Run resource saturation`: opens when P95 CPU or memory stays
  above 85% for ten minutes.
- `Athena agent error log`: opens on ADK `ERROR` logs and limits repeated email
  notifications to one per 15 minutes.

All policies send notifications to the `Athena operations email` channel.

The custom `Athena Production Operations` dashboard shows:

- request rate and HTTP 5xx rate per service;
- P95 request latency;
- active instances, P95 CPU and P95 memory utilization;
- open incidents;
- recent Cloud Run request logs, warnings/errors, and agent telemetry metadata.

The dashboard definition is versioned at `deploy/monitoring-dashboard.json`.

Operational pages:

- Monitoring > Uptime checks: endpoint status and latency by region.
- Monitoring > Alerting: open incidents and policy configuration.
- Cloud Run > service > Metrics: requests, latency, instances, CPU and memory.
- Cloud Run > service > Logs: stack traces and request logs.
- Trace > Trace explorer: individual ADK agent, LLM and tool spans.
- Cloud Build > History: identify the commit and failed deployment step.
- Artifact Registry > athena: image size and cleanup policy.

## Agent telemetry and privacy

The ADK runtime exports OpenTelemetry spans to Cloud Trace. A trace contains
agent hand-offs, model calls, tool calls, duration and error metadata. The
runtime sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT`, so
prompt text, response text, tokens, credentials, medical records and HTTP
request bodies aren't captured.

To inspect a failed request:

1. Open the dashboard's `Warnings and errors` or `Recent HTTP requests` panel.
2. Open the log entry and copy its trace identifier when available.
3. Open Trace explorer, filter `service.name=athena-adk`, and select the matching
   trace.
4. Expand `invoke_agent`, model and `execute_tool` spans to find the slow or
   failed operation.

Useful Cloud Logging queries:

```text
resource.type="cloud_run_revision"
resource.labels.service_name=~"athena-(adk|auth|booking)"
logName="projects/project-5d300c02-d165-4037-b6f/logs/run.googleapis.com%2Frequests"
```

```text
resource.type="cloud_run_revision"
resource.labels.service_name="athena-adk"
severity>=ERROR
```

## Custom-domain activation

There are two independent statuses:

1. Cloudflare dashboard > `mchienn.dev` > Overview. The zone must be `Active`.
2. Firebase Console > Hosting > Add custom domain / custom domains. For both
   `mchienn.dev` and `www.mchienn.dev`, ownership and certificate must be active.

During activation, `HOST_ACTIVE` with `CERT_VALIDATING` or `CERT_PROPAGATING`
means DNS is visible but Firebase is still issuing or distributing the TLS
certificate. Do not add a production uptime check for `mchienn.dev` until HTTPS
returns a valid certificate. The stable fallback remains
`https://project-5d300c02-d165-4037-b6f.web.app`.

## First response to an incident

1. Open the failed uptime check and identify the endpoint and affected regions.
2. Check the latest Cloud Build result and its commit SHA.
3. Check Cloud Run logs for the affected service and compare the latest ready
   revision with the previous revision.
4. If the latest revision caused the failure, route traffic back to the previous
   healthy revision, then investigate without keeping production down.
5. For a frontend-only issue, use Firebase Hosting Release history > Roll back.
