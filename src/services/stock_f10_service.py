from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.providers.f10.mootdx_f10 import SECTION_MAP
from src.schemas import F10Data, F10Response
from src.utils.symbols import normalize_symbol


class StockF10Service:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_f10(self, symbol: str, *, section: str, max_chars: int) -> F10Response:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="F10 is supported for A-shares only in v1.",
            )
        text = await self.provider.get_f10(normalized, section)
        truncated = len(text) > max_chars
        return F10Response(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=F10Data(
                symbol=normalized,
                section=section,
                provider_section=SECTION_MAP[section],
                text=text[:max_chars],
                truncated=truncated,
            ),
        )
