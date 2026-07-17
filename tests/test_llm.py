from unittest.mock import patch

from hanoi_heart_assistant.llm import _openai_client, get_adk_model


def test_openai_client_accepts_static_api_key() -> None:
    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-api-key",
            "OPENAI_BASE_URL": "https://example.test/v1",
        },
        clear=False,
    ):
        client = _openai_client()
    try:
        assert client.api_key == "test-api-key"
        assert str(client.base_url) == "https://example.test/v1/"
    finally:
        client.close()


def test_adk_model_uses_openai_compatible_provider() -> None:
    get_adk_model.cache_clear()
    with patch.dict(
        "os.environ",
        {"HOSPITAL_ASSISTANT_MODEL": "google/gemini-2.5-flash"},
        clear=False,
    ):
        model = get_adk_model()
    assert model.model == "openai/google/gemini-2.5-flash"
    get_adk_model.cache_clear()
