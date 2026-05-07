from restaurant_agent.config import Settings


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
