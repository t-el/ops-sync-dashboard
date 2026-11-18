from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class Settings:
    database_path: str = field(default_factory=lambda: _env("DATABASE_PATH", "data/ops.db"))
    stripe_api_base: str = field(default_factory=lambda: _env("STRIPE_API_BASE", "http://127.0.0.1:9100/stripe"))
    stripe_api_key: str = field(default_factory=lambda: _env("STRIPE_API_KEY", "sk_test_mock"))
    helpdesk_api_base: str = field(default_factory=lambda: _env("HELPDESK_API_BASE", "http://127.0.0.1:9100/helpdesk"))
    helpdesk_api_key: str = field(default_factory=lambda: _env("HELPDESK_API_KEY", "hd_mock"))
    sync_interval_seconds: int = field(default_factory=lambda: int(_env("SYNC_INTERVAL_SECONDS", "900")))
    scheduler_enabled: bool = field(default_factory=lambda: _env("SCHEDULER_ENABLED", "true").lower() == "true")
    retry_attempts: int = field(default_factory=lambda: int(_env("RETRY_ATTEMPTS", "3")))
    retry_base_delay: float = field(default_factory=lambda: float(_env("RETRY_BASE_DELAY", "1.0")))
    request_timeout: float = field(default_factory=lambda: float(_env("REQUEST_TIMEOUT", "15")))
    admin_token: str = field(default_factory=lambda: _env("ADMIN_TOKEN", ""))
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:3000"))
