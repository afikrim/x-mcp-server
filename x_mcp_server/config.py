"""Runtime configuration, loaded from environment variables (and an optional .env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings. All fields are overridable via ``X_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="X_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Authentication
    auth_token: str | None = None
    csrf_token: str | None = None

    # Browser
    headless: bool = True
    user_data_dir: str = ".x-mcp-data"
    browser_channel: str = "chrome"
    nav_timeout_ms: int = 30_000

    # Logging
    log_level: str = "INFO"

    @property
    def has_session_cookies(self) -> bool:
        return bool(self.auth_token)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
