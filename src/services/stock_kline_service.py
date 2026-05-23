from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import KlineRequest, KlineResponse
from src.utils.symbols import normalize_symbol


class StockKlineService:
    def __init__(self, *, a_share_provider: Any, hk_provider: Any = None) -> None:
        self.a_share_provider = a_share_provider
        self.hk_provider = hk_provider

    async def get_kline(self, request: KlineRequest) -> KlineResponse:
        symbol = normalize_symbol(request.symbol)
        if request.adjust != "none":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_ADJUSTMENT,
                provider=None,
                message="Adjusted K-line data is not supported by the v1 default provider.",
            )
        if symbol.market == "hk" and self.hk_provider is None:
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Hong Kong K-line data is not supported in v1.",
            )
        if symbol.market == "a_share" and self.a_share_provider is None:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=None,
                message="A-share K-line provider is not configured.",
            )
        provider = self.a_share_provider if symbol.market == "a_share" else self.hk_provider
        data = await provider.get_kline(symbol, request)
        return KlineResponse(
            status="ok",
            provider=provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=data,
        )
