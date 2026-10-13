"""Server-only configuration. Secrets never enter the Gradio component tree."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///data/fleetops.db"
    api_token: str = field(default="", repr=False)
    ai_mode: str = "baseline"
    ai_base_url: str = "https://integrate.api.nvidia.com/v1"
    ai_model: str = ""
    ai_api_key: str = field(default="", repr=False)
    ai_max_steps: int = 6
    ai_timeout: float = 20.0
    otlp_endpoint: str = ""
    log_path: str = ""
    max_sessions: int = 128
    session_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("FLEETOPS_DATABASE_URL", "sqlite:///data/fleetops.db"),
            api_token=os.getenv("FLEETOPS_API_TOKEN", ""),
            ai_mode=os.getenv("FLEETOPS_AI_MODE", "baseline"),
            ai_base_url=os.getenv("FLEETOPS_AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            ai_model=os.getenv("FLEETOPS_AI_MODEL", ""),
            ai_api_key=os.getenv("FLEETOPS_AI_API_KEY", ""),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            log_path=os.getenv("FLEETOPS_LOG_PATH", ""),
        )

    def __post_init__(self) -> None:
        if self.ai_mode not in {"baseline", "live"}:
            raise ValueError("FLEETOPS_AI_MODE must be baseline or live")
        if not 1 <= self.ai_max_steps <= 12:
            raise ValueError("AI step limit must be between 1 and 12")
        if self.ai_timeout <= 0 or self.max_sessions < 1 or self.session_ttl_seconds < 1:
            raise ValueError("Timeout, session capacity, and TTL must be positive")
        if self.ai_mode == "live" and (not self.ai_api_key or not self.ai_model):
            raise ValueError("Live AI requires FLEETOPS_AI_API_KEY and FLEETOPS_AI_MODEL")
        if self.ai_mode == "live" and not self.ai_base_url.startswith("https://"):
            raise ValueError("Live AI requires an HTTPS provider endpoint")
