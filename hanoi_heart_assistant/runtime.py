"""Cloud Run entrypoints for the independently deployed Athena services."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from starlette.responses import PlainTextResponse


class PrefixStripMiddleware:
    """Expose an ASGI HTTP app below a proxy prefix while preserving lifespan."""

    def __init__(self, app: Any, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path != self.prefix and not path.startswith(f"{self.prefix}/"):
            await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)
            return

        inner_scope = dict(scope)
        inner_path = path[len(self.prefix) :] or "/"
        inner_scope["path"] = inner_path
        inner_scope["raw_path"] = inner_path.encode("utf-8")
        inner_scope["root_path"] = f"{scope.get('root_path', '')}{self.prefix}"
        await self.app(inner_scope, receive, send)

def command_for_target(target: str, *, port: int) -> list[str]:
    """Return the process command for a Cloud Run service target."""
    common = ["--host", "0.0.0.0", "--port", str(port)]
    if target == "adk":
        return ["uvicorn", "hanoi_heart_assistant.adk_runtime:app", *common]
    if target == "auth":
        return ["uvicorn", "hanoi_heart_assistant.auth.main:app", *common]
    if target == "booking":
        return ["uvicorn", "hanoi_heart_assistant.booking_runtime:app", *common]
    raise ValueError(f"Unsupported SERVICE_TARGET: {target!r}")


def target_from_environment(environment: Mapping[str, str]) -> str:
    explicit_target = environment.get("SERVICE_TARGET", "").strip().lower()
    if explicit_target:
        return explicit_target
    service_name = environment.get("K_SERVICE", "").strip().lower()
    if service_name.startswith("athena-"):
        return service_name.removeprefix("athena-")
    return ""


def main() -> None:
    target = target_from_environment(os.environ)
    port = int(os.getenv("PORT", "8080"))
    command = command_for_target(target, port=port)
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
