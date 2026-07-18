"""Small, privacy-safe ingestion endpoint for browser telemetry."""

from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .observability import emit_event

_IDENTIFIER = re.compile(
    r"^(?:\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[A-Za-z0-9_-]{24,})$",
    re.IGNORECASE,
)
_recent_events: deque[float] = deque()
_rate_lock = threading.Lock()


def _accept_event() -> bool:
    now = time.monotonic()
    try:
        limit = max(1, int(os.getenv("FRONTEND_TELEMETRY_MAX_EVENTS_PER_MINUTE", "300")))
    except ValueError:
        limit = 300
    with _rate_lock:
        while _recent_events and now - _recent_events[0] >= 60:
            _recent_events.popleft()
        if len(_recent_events) >= limit:
            return False
        _recent_events.append(now)
    return True


def sanitize_route(value: str) -> str:
    path = urlsplit(value).path or "/"
    segments = [":id" if _IDENTIFIER.fullmatch(item) else item for item in path.split("/")]
    return "/".join(segments)[:160] or "/"


class FrontendTelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["error", "web_vital"]
    source: Literal["window_error", "unhandled_rejection", "react_error"] | None = None
    route: str = Field(default="/", min_length=1, max_length=256)
    error_name: str | None = Field(default=None, min_length=1, max_length=64)
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{16,64}$")
    release: str | None = Field(default=None, max_length=64)
    metric_name: Literal["LCP", "INP", "CLS", "FCP", "TTFB"] | None = None
    metric_value: float | None = Field(default=None, ge=0, le=10_000_000)
    rating: Literal["good", "needs-improvement", "poor"] | None = None
    navigation_type: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_kind_fields(self) -> FrontendTelemetryPayload:
        if self.kind == "error" and not all(
            (self.source, self.error_name, self.fingerprint)
        ):
            raise ValueError("error telemetry requires source, error_name and fingerprint")
        if self.kind == "web_vital" and not all(
            (self.metric_name, self.metric_value is not None, self.rating)
        ):
            raise ValueError("web vital telemetry requires name, value and rating")
        return self


def create_telemetry_router() -> APIRouter:
    router = APIRouter(tags=["telemetry"])

    @router.post("/telemetry/frontend", status_code=status.HTTP_202_ACCEPTED)
    async def frontend_telemetry(payload: FrontendTelemetryPayload) -> dict[str, str]:
        if not _accept_event():
            raise HTTPException(status_code=429, detail="Telemetry rate limit exceeded")
        route = sanitize_route(payload.route)
        if payload.kind == "error":
            fields = {
                "telemetry_type": "frontend",
                "outcome": "failure",
                "source": payload.source,
                "route": route,
                "error_name": payload.error_name,
                "fingerprint": payload.fingerprint,
            }
            if payload.release:
                fields["release"] = payload.release
            emit_event("frontend_error", **fields)
        else:
            fields = {
                "telemetry_type": "frontend",
                "outcome": payload.rating,
                "route": route,
                "metric_name": payload.metric_name,
                "metric_value": payload.metric_value,
                "rating": payload.rating,
                "navigation_type": payload.navigation_type,
            }
            if payload.release:
                fields["release"] = payload.release
            emit_event("web_vital", **fields)
        return {"status": "accepted"}

    return router


router = create_telemetry_router()


__all__ = ["FrontendTelemetryPayload", "create_telemetry_router", "router", "sanitize_route"]
