import os
import subprocess
import sys

from fastapi.testclient import TestClient

from hanoi_heart_assistant.booking_runtime import app as booking_app
from hanoi_heart_assistant.runtime import (
    PrefixStripMiddleware,
    command_for_target,
    target_from_environment,
)


def test_adk_runtime_uses_cloud_run_host_port_and_hosting_prefix() -> None:
    command = command_for_target("adk", port=8080)

    assert command == [
        "uvicorn",
        "hanoi_heart_assistant.adk_runtime:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]


def test_fastapi_runtime_commands_use_cloud_run_port() -> None:
    assert command_for_target("auth", port=9090) == [
        "uvicorn",
        "hanoi_heart_assistant.auth.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "9090",
    ]
    assert command_for_target("booking", port=9090) == [
        "uvicorn",
        "hanoi_heart_assistant.booking_runtime:app",
        "--host",
        "0.0.0.0",
        "--port",
        "9090",
    ]


def test_booking_app_accepts_firebase_hosting_prefix() -> None:
    response = TestClient(booking_app).get("/booking-api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_cloud_run_service_name_selects_runtime_target() -> None:
    assert target_from_environment({"K_SERVICE": "athena-adk"}) == "adk"
    assert target_from_environment({"K_SERVICE": "athena-auth"}) == "auth"
    assert target_from_environment({"SERVICE_TARGET": "booking"}) == "booking"


def test_adk_runtime_import_does_not_require_auth_secret() -> None:
    environment = os.environ.copy()
    environment.pop("JWT_SECRET_KEY", None)

    result = subprocess.run(
        [sys.executable, "-c", "import hanoi_heart_assistant.runtime"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_prefix_middleware_exposes_inner_api_under_hosting_prefix() -> None:
    from fastapi import FastAPI

    inner = FastAPI()

    @inner.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    prefixed_app = PrefixStripMiddleware(inner, "/adk-api")

    assert TestClient(prefixed_app).get("/adk-api/health").status_code == 200
    assert TestClient(prefixed_app).get("/health").status_code == 404
