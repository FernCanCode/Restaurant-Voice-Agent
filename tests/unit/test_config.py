import pytest

from restaurant_agent.config import Settings


@pytest.fixture(autouse=True)
def _clear_optional_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ENABLE_TWILIO", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "")
    monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "")


def test_settings_load_with_defaults():
    settings = Settings()
    assert settings.app_env == "local"
    assert settings.enable_twilio is False
    assert settings.enable_browser_voice is True


def test_anthropic_key_is_optional():
    settings = Settings()
    assert settings.anthropic_api_key is None


def test_twilio_credentials_optional():
    settings = Settings()
    assert settings.enable_twilio is False
    assert settings.twilio_account_sid is None
    assert settings.twilio_auth_token is None
