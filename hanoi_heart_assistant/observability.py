"""Privacy-safe structured telemetry for Cloud Logging and Cloud Trace correlation."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_ALLOWED_FIELDS = {
    "telemetry_type",
    "outcome",
    "service",
    "operation",
    "route",
    "method",
    "status_code",
    "status_class",
    "duration_ms",
    "agent_name",
    "model_name",
    "finish_reason",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "tool_name",
    "error_type",
    "source",
    "error_name",
    "fingerprint",
    "metric_name",
    "metric_value",
    "rating",
    "navigation_type",
    "release",
    "environment",
}
_TRACE_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_BUSINESS_OPERATIONS = {
    "register",
    "login",
    "refresh_access_token",
    "logout",
    "create_appointment",
}
_timings: dict[tuple[str, ...], list[float]] = defaultdict(list)
_timings_lock = threading.Lock()


def _safe_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = getattr(value, "value", value)
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    return text[:160]


def emit_event(event_name: str, *, severity: str = "INFO", **fields: Any) -> None:
    """Write one allowlisted JSON event; arbitrary caller fields are discarded."""
    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": severity,
        "event_name": _safe_value(event_name),
    }
    for key, value in fields.items():
        if key in _ALLOWED_FIELDS and value is not None:
            payload[key] = _safe_value(value)

    trace_id = fields.get("trace_id")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if project and isinstance(trace_id, str) and _TRACE_RE.fullmatch(trace_id):
        payload["logging.googleapis.com/trace"] = f"projects/{project}/traces/{trace_id}"

    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def _timing_key(context: Any, operation: str, subject: str = "") -> tuple[str, ...]:
    return (
        operation,
        str(getattr(context, "invocation_id", "")),
        str(getattr(context, "agent_name", "unknown")),
        subject,
    )


def _start_timing(key: tuple[str, ...]) -> None:
    with _timings_lock:
        _timings[key].append(time.perf_counter())


def _finish_timing(key: tuple[str, ...]) -> float | None:
    with _timings_lock:
        values = _timings.get(key)
        if not values:
            return None
        started = values.pop()
        if not values:
            _timings.pop(key, None)
    return round((time.perf_counter() - started) * 1000, 2)


def before_model_callback(context: Any, _: Any) -> None:
    _start_timing(_timing_key(context, "model"))


def after_model_callback(context: Any, response: Any) -> None:
    usage = getattr(response, "usage_metadata", None)
    error_code = getattr(response, "error_code", None)
    duration_ms = _finish_timing(_timing_key(context, "model"))
    fields: dict[str, Any] = {
        "telemetry_type": "agent",
        "outcome": "failure" if error_code else "success",
        "agent_name": getattr(context, "agent_name", "unknown"),
        "model_name": getattr(response, "model_version", "unknown"),
        "finish_reason": getattr(response, "finish_reason", None),
    }
    if duration_ms is not None:
        fields["duration_ms"] = duration_ms
    if usage is not None:
        fields.update(
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            total_tokens=getattr(usage, "total_token_count", None),
            cached_tokens=getattr(usage, "cached_content_token_count", None),
            reasoning_tokens=getattr(usage, "thoughts_token_count", None),
        )
    emit_event("model_call", severity="ERROR" if error_code else "INFO", **fields)


def on_model_error_callback(context: Any, _: Any, error: Exception) -> None:
    emit_event(
        "model_call",
        severity="ERROR",
        telemetry_type="agent",
        outcome="failure",
        agent_name=getattr(context, "agent_name", "unknown"),
        duration_ms=_finish_timing(_timing_key(context, "model")),
        error_type=type(error).__name__,
    )


def before_tool_callback(tool: Any, _: dict[str, Any], context: Any) -> None:
    name = str(getattr(tool, "name", None) or getattr(tool, "__name__", "unknown"))
    _start_timing(_timing_key(context, "tool", name))


def after_tool_callback(
    tool: Any,
    _: dict[str, Any],
    context: Any,
    tool_response: dict[str, Any],
) -> None:
    name = str(getattr(tool, "name", None) or getattr(tool, "__name__", "unknown"))
    failed = isinstance(tool_response, dict) and bool(tool_response.get("error"))
    emit_event(
        "tool_call",
        severity="ERROR" if failed else "INFO",
        telemetry_type="agent",
        outcome="failure" if failed else "success",
        agent_name=getattr(context, "agent_name", "unknown"),
        tool_name=name,
        duration_ms=_finish_timing(_timing_key(context, "tool", name)),
    )


def on_tool_error_callback(
    tool: Any,
    _: dict[str, Any],
    context: Any,
    error: Exception,
) -> None:
    name = str(getattr(tool, "name", None) or getattr(tool, "__name__", "unknown"))
    emit_event(
        "tool_call",
        severity="ERROR",
        telemetry_type="agent",
        outcome="failure",
        agent_name=getattr(context, "agent_name", "unknown"),
        tool_name=name,
        duration_ms=_finish_timing(_timing_key(context, "tool", name)),
        error_type=type(error).__name__,
    )


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Emit sanitized business and ADK request outcomes without request content."""

    def __init__(self, app: Any, service_name: str | None = None) -> None:
        super().__init__(app)
        self.service_name = service_name or os.getenv("K_SERVICE", "local")

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route_object = request.scope.get("route")
            route = str(getattr(route_object, "path", request.url.path))
            operation = str(getattr(route_object, "name", "unknown"))
            is_agent = request.method == "POST" and (
                route.endswith("/run") or "/apps/" in route
            )
            is_business = operation in _BUSINESS_OPERATIONS
            if is_agent or is_business or status_code >= 500:
                if status_code < 400:
                    outcome = "success"
                elif status_code < 500:
                    outcome = "client_error"
                else:
                    outcome = "server_error"
                trace_header = request.headers.get("x-cloud-trace-context", "")
                trace_id = trace_header.split("/", 1)[0]
                emit_event(
                    "agent_request" if is_agent else "business_request",
                    severity="ERROR" if status_code >= 500 else "INFO",
                    telemetry_type="agent_http" if is_agent else "business",
                    outcome=outcome,
                    service=self.service_name,
                    operation=operation,
                    route=route,
                    method=request.method,
                    status_code=status_code,
                    status_class=f"{status_code // 100}xx",
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    trace_id=trace_id,
                )


def agent_observability_callbacks() -> dict[str, Any]:
    """Return the callback set shared by every ADK LLM agent."""
    return {
        "before_model_callback": before_model_callback,
        "after_model_callback": after_model_callback,
        "on_model_error_callback": on_model_error_callback,
        "before_tool_callback": before_tool_callback,
        "after_tool_callback": after_tool_callback,
        "on_tool_error_callback": on_tool_error_callback,
    }
