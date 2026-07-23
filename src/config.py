from __future__ import annotations

import logging
import os
from functools import cache
from ipaddress import ip_address

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="127.0.0.1", alias="AGENTEUM_HOST")
    port: int = Field(default=8766, alias="AGENTEUM_PORT")
    allow_remote: bool = Field(default=False, alias="AGENTEUM_ALLOW_REMOTE")
    fin_request_timeout: float = Field(default=15.0, alias="AGENTEUM_FIN_REQUEST_TIMEOUT")
    fin_retry_attempts: int = Field(default=1, alias="AGENTEUM_FIN_RETRY_ATTEMPTS")
    fin_retry_backoff_seconds: float = Field(
        default=0.5,
        alias="AGENTEUM_FIN_RETRY_BACKOFF_SECONDS",
    )
    fin_a_kline_provider: str = Field(default="tencent", alias="AGENTEUM_FIN_A_KLINE_PROVIDER")
    fin_hk_kline_provider: str = Field(default="tencent", alias="AGENTEUM_FIN_HK_KLINE_PROVIDER")
    fin_profile_provider: str = Field(default="tencent", alias="AGENTEUM_FIN_PROFILE_PROVIDER")
    fin_financial_statements_provider: str = Field(
        default="sina",
        alias="AGENTEUM_FIN_FINANCIAL_STATEMENTS_PROVIDER",
    )
    fin_f10_provider: str = Field(default="eastmoney", alias="AGENTEUM_FIN_F10_PROVIDER")
    fin_announcements_provider: str = Field(
        default="cninfo",
        alias="AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER",
    )
    fin_iwencai_provider: str = Field(default="iwencai", alias="AGENTEUM_FIN_IWENCAI_PROVIDER")
    fin_iwencai_api_key: str | None = Field(default=None, alias="AGENTEUM_FIN_IWENCAI_API_KEY")

    @property
    def resolved_iwencai_api_key(self) -> str | None:
        """Iwencai API key: explicit setting first, then the IWENCAI_API_KEY env convention."""
        return self.fin_iwencai_api_key or os.environ.get("IWENCAI_API_KEY") or None

    def validate_network_binding(self, logger: logging.Logger) -> None:
        if not is_remote_bind_host(self.host):
            return
        if not self.allow_remote:
            raise ValueError(
                "Remote bind hosts require AGENTEUM_ALLOW_REMOTE=true "
                "because v1 has no authentication."
            )
        logger.warning(
            "Agenteum Fin is listening on a remote bind host with no authentication.",
            extra={"host": self.host, "port": self.port, "security": "no_authentication"},
        )


def is_remote_bind_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return False
    if normalized in {"0.0.0.0", "::", ""}:
        return True
    try:
        return not ip_address(normalized).is_loopback
    except ValueError:
        return True


@cache
def get_settings() -> Settings:
    return Settings()
