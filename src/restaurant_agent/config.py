from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "",
    "replace_me",
    "your_key_here",
    "sk-placeholder",
    "change_me",
}


class Settings(BaseSettings):
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-haiku-4-5"

    enable_twilio: bool = False
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    twilio_webhook_base_url: Optional[str] = None

    enable_browser_voice: bool = True

    menu_raw_fixture_path: str = "data/raw/sample_restaurant_menu.html"
    menu_data_path: str = "data/processed/menu.json"
    menu_index_path: str = "data/index"

    hf_home: str = ".cache/huggingface"
    transformers_cache: str = ".cache/huggingface"

    enable_debug_routes: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator(
        "anthropic_api_key",
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_phone_number",
        "twilio_webhook_base_url",
        mode="before",
    )
    @classmethod
    def normalize_placeholder_secrets(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if normalized.lower() in _PLACEHOLDER_SECRETS:
            return None
        return normalized


def get_settings() -> Settings:
    return Settings()
