"""OpenAI-compatible ADK model configured with API key or Google ADC."""

import os
from functools import lru_cache
from threading import Lock
from typing import Any

import google.auth
from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from openai import OpenAI

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_credential_lock = Lock()


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc: {name}")
    return value


@lru_cache(maxsize=1)
def _google_credentials() -> Credentials:
    credentials, _ = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
    return credentials


def _api_key() -> str:
    """Return a static API key, or a refreshed Google OAuth access token."""
    static_key = os.getenv("OPENAI_API_KEY", "").strip()
    if static_key:
        return static_key

    credentials = _google_credentials()
    with _credential_lock:
        if not credentials.valid:
            credentials.refresh(Request())
        if not credentials.token:
            raise RuntimeError("Không lấy được access token từ Google ADC.")
        return credentials.token


def _openai_client() -> OpenAI:
    """Create an OpenAI client for direct calls to the compatible endpoint."""
    return OpenAI(
        api_key=_api_key(),
        base_url=_required_env("OPENAI_BASE_URL"),
    )


class RefreshingAuthLiteLLMClient(LiteLLMClient):
    """Refresh Google ADC before each LiteLLM request used by ADK."""

    async def acompletion(
        self,
        model: Any,
        messages: Any,
        tools: Any,
        **kwargs: Any,
    ) -> Any:
        kwargs.update(api_key=_api_key(), api_base=_required_env("OPENAI_BASE_URL"))
        return await super().acompletion(model, messages, tools, **kwargs)

    def completion(
        self,
        model: Any,
        messages: Any,
        tools: Any,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        kwargs.update(api_key=_api_key(), api_base=_required_env("OPENAI_BASE_URL"))
        return super().completion(model, messages, tools, stream, **kwargs)


@lru_cache(maxsize=1)
def get_adk_model() -> LiteLlm:
    model_name = os.getenv(
        "HOSPITAL_ASSISTANT_MODEL",
        "google/gemini-3-flash-preview",
    ).strip()

    if not model_name:
        raise RuntimeError("HOSPITAL_ASSISTANT_MODEL không được để trống.")

    if not model_name.startswith("openai/"):
        model_name = f"openai/{model_name}"

    return LiteLlm(
        model=model_name,
        llm_client=RefreshingAuthLiteLLMClient(),
        reasoning_effort="low",
        allowed_openai_params=["reasoning_effort"],
    )