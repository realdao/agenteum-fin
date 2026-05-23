from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ProviderError, is_recoverable
from src.schemas import FallbackRecord, StockProfileResponse
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol


class StockProfileService:
    def __init__(self, *, providers: list[Any], retry_policy: RetryPolicy | None = None) -> None:
        self.providers = providers
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_profile(self, symbol: str) -> StockProfileResponse:
        normalized = normalize_symbol(symbol)
        fallbacks: list[FallbackRecord] = []
        last_error: ProviderError | None = None
        for index, provider in enumerate(self.providers):
            try:
                data = await logged_provider_call(
                    operation="stock_profile",
                    provider=provider.name,
                    symbol=normalized,
                    fallback_count=len(fallbacks),
                    call=lambda provider=provider: run_with_retries(
                        lambda: provider.get_profile(normalized),
                        policy=self.retry_policy,
                    ),
                )
                return StockProfileResponse(
                    status="ok",
                    provider=provider.name,
                    provider_status="ok" if not fallbacks else "fallback",
                    fetched_at=datetime.now(UTC).isoformat(),
                    fallbacks=fallbacks,
                    data=data,
                )
            except ProviderError as exc:
                if not is_recoverable(exc.error_type) or index == len(self.providers) - 1:
                    exc.fallbacks = fallbacks
                    raise
                next_provider = self.providers[index + 1]
                fallbacks.append(
                    FallbackRecord(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                        reason=exc.error_type.value,
                    )
                )
                last_error = exc
        if last_error is not None:
            last_error.fallbacks = fallbacks
            raise last_error
        raise RuntimeError("StockProfileService requires at least one provider.")
