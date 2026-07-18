import io
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hanoi_heart_assistant.observability import (
    TelemetryMiddleware,
    after_model_callback,
    emit_event,
)
from hanoi_heart_assistant.telemetry_api import create_telemetry_router


def test_emit_event_outputs_allowlisted_structured_json(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr("sys.stdout", output)

    emit_event(
        "model_call",
        telemetry_type="agent",
        outcome="success",
        agent_name="appointment_agent",
        total_tokens=42,
        ignored_patient_name="must-not-be-logged",
    )

    payload = json.loads(output.getvalue())
    assert payload["event_name"] == "model_call"
    assert payload["agent_name"] == "appointment_agent"
    assert payload["total_tokens"] == 42
    assert "ignored_patient_name" not in payload
    assert "must-not-be-logged" not in output.getvalue()


def test_after_model_callback_records_usage_without_message_content(monkeypatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "hanoi_heart_assistant.observability.emit_event",
        lambda event_name, **fields: events.append({"event_name": event_name, **fields}),
    )
    context = SimpleNamespace(agent_name="service_price_agent")
    response = SimpleNamespace(
        model_version="gemini-test",
        finish_reason="STOP",
        error_code=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=11,
            candidates_token_count=7,
            total_token_count=18,
            cached_content_token_count=3,
            thoughts_token_count=2,
        ),
        content="private response content",
    )

    assert after_model_callback(context, response) is None

    assert events == [
        {
            "event_name": "model_call",
            "severity": "INFO",
            "telemetry_type": "agent",
            "outcome": "success",
            "agent_name": "service_price_agent",
            "model_name": "gemini-test",
            "finish_reason": "STOP",
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
            "cached_tokens": 3,
            "reasoning_tokens": 2,
        }
    ]


def test_http_middleware_logs_route_template_not_identifier(monkeypatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "hanoi_heart_assistant.observability.emit_event",
        lambda event_name, **fields: events.append({"event_name": event_name, **fields}),
    )
    app = FastAPI()
    app.add_middleware(TelemetryMiddleware, service_name="test-service")

    @app.post("/appointments/{appointment_id}", name="create_appointment")
    def appointment(appointment_id: str) -> dict[str, str]:
        return {"id": appointment_id}

    response = TestClient(app).post("/appointments/private-123?phone=0900000000")

    assert response.status_code == 200
    assert events[0]["event_name"] == "business_request"
    assert events[0]["route"] == "/appointments/{appointment_id}"
    assert events[0]["operation"] == "create_appointment"
    serialized = json.dumps(events)
    assert "private-123" not in serialized
    assert "0900000000" not in serialized


def test_frontend_telemetry_endpoint_accepts_safe_payload_only(monkeypatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "hanoi_heart_assistant.telemetry_api.emit_event",
        lambda event_name, **fields: events.append({"event_name": event_name, **fields}),
    )
    app = FastAPI()
    app.include_router(create_telemetry_router(), prefix="/api")
    client = TestClient(app)

    response = client.post(
        "/api/telemetry/frontend",
        json={
            "kind": "error",
            "source": "window_error",
            "route": "/appointments/91d88b75-9c8e-4dd2-a49a-1645874acc33",
            "error_name": "TypeError",
            "fingerprint": "a" * 32,
            "release": "commit-sha",
        },
    )

    assert response.status_code == 202
    assert events[0]["event_name"] == "frontend_error"
    assert events[0]["route"] == "/appointments/:id"

    rejected = client.post(
        "/api/telemetry/frontend",
        json={"kind": "error", "message": "patient private content"},
    )
    assert rejected.status_code == 422


def test_frontend_web_vital_is_recorded_as_numeric_metric(monkeypatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "hanoi_heart_assistant.telemetry_api.emit_event",
        lambda event_name, **fields: events.append({"event_name": event_name, **fields}),
    )
    app = FastAPI()
    app.include_router(create_telemetry_router(), prefix="/api")

    response = TestClient(app).post(
        "/api/telemetry/frontend",
        json={
            "kind": "web_vital",
            "route": "/",
            "metric_name": "LCP",
            "metric_value": 1234.5,
            "rating": "good",
            "navigation_type": "navigate",
        },
    )

    assert response.status_code == 202
    assert events == [
        {
            "event_name": "web_vital",
            "telemetry_type": "frontend",
            "outcome": "good",
            "route": "/",
            "metric_name": "LCP",
            "metric_value": 1234.5,
            "rating": "good",
            "navigation_type": "navigate",
        }
    ]
