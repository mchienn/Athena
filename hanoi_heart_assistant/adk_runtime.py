"""ASGI entrypoint exposing Google ADK below the Firebase Hosting prefix."""

from google.adk.cli.fast_api import get_fast_api_app

from hanoi_heart_assistant.runtime import PrefixStripMiddleware

adk_app = get_fast_api_app(
    agents_dir=".",
    session_service_uri="memory://",
    artifact_service_uri="memory://",
    memory_service_uri="memory://",
    use_local_storage=False,
    allow_origins=[],
    web=False,
    url_prefix="/adk-api",
    otel_to_cloud=True,
)

app = PrefixStripMiddleware(adk_app, "/adk-api")
