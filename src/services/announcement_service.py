from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import AnnouncementsData, AnnouncementsResponse
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol


class AnnouncementService:
    def __init__(self, *, provider: Any, retry_policy: RetryPolicy | None = None) -> None:
        self.provider = provider
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_announcements(self, symbol: str, *, page_size: int) -> AnnouncementsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Announcements are supported for A-shares only in v1.",
            )
        if self.provider is None:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=None,
                message="Announcements provider is not configured.",
            )
        announcements = await logged_provider_call(
            operation="stock_announcements",
            provider=self.provider.name,
            symbol=normalized,
            fallback_count=0,
            call=lambda: run_with_retries(
                lambda: self.provider.get_announcements(normalized, page_size),
                policy=self.retry_policy,
            ),
        )
        return AnnouncementsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=AnnouncementsData(symbol=normalized, announcements=announcements),
        )
