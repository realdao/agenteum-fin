from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import AnnouncementsData, AnnouncementsResponse
from src.utils.symbols import normalize_symbol


class AnnouncementService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_announcements(self, symbol: str, *, page_size: int) -> AnnouncementsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Announcements are supported for A-shares only in v1.",
            )
        announcements = await self.provider.get_announcements(normalized, page_size)
        return AnnouncementsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=AnnouncementsData(symbol=normalized, announcements=announcements),
        )
