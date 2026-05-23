from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import KlineRequest, KlineResponse
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol


class StockKlineService:
    def __init__(
        self,
        *,
        a_share_provider: Any,
        hk_provider: Any = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.a_share_provider = a_share_provider
        self.hk_provider = hk_provider
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_kline(self, request: KlineRequest) -> KlineResponse:
        symbol = normalize_symbol(request.symbol)
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
        supported_adjustments = getattr(provider, "supported_adjustments", {"none"})
        if request.adjust not in supported_adjustments:
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_ADJUSTMENT,
                provider=provider.name,
                message=f"K-line adjustment mode is not supported: {request.adjust}",
            )
        data = await logged_provider_call(
            operation="stock_kline",
            provider=provider.name,
            symbol=symbol,
            fallback_count=0,
            call=lambda: run_with_retries(
                lambda: provider.get_kline(symbol, request),
                policy=self.retry_policy,
            ),
        )
        return KlineResponse(
            status="ok",
            provider=provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=data,
        )
