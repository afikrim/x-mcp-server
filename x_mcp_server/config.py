"""Runtime configuration, loaded from environment variables (and an optional .env)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import field_validator
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
    # Optional credentials for the (best-effort, fragile) automated DOM login.
    # Prefer the interactive `login` tool or session cookies over these.
    username: str | None = None
    password: str | None = None

    # Browser
    headless: bool = True
    user_data_dir: str = "~/.x-mcp/profile"
    browser_channel: str = "chrome"
    nav_timeout_ms: int = 30_000
    # How many times to retry a navigation that fails with a transient network
    # error (e.g. ERR_NETWORK_CHANGED, connection resets) before giving up.
    nav_retries: int = 3
    # How long the interactive `login` tool waits for the user to finish signing in.
    login_timeout_ms: int = 180_000

    # Logging
    log_level: str = "INFO"

    @field_validator("user_data_dir")
    @classmethod
    def _expand_user_data_dir(cls, value: str) -> str:
        """Resolve ``~`` and ``$VAR`` once at load time so every consumer gets an
        absolute path. Handles both ``~/.x-mcp/profile`` and ``$HOME/...`` forms,
        cross-platform, instead of relying on each call site to remember to expand.
        """
        return str(Path(os.path.expandvars(value)).expanduser())

    @property
    def has_session_cookies(self) -> bool:
        return bool(self.auth_token)

    @property
    def has_credentials(self) -> bool:
        return bool(self.username and self.password)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
