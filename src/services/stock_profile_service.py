from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError, is_recoverable
from src.schemas import (
    ErrorDetail,
    FallbackRecord,
    StockProfileData,
    StockProfileItemError,
    StockProfileResponse,
    StockProfilesData,
)
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import NormalizedSymbol, normalize_symbol


class StockProfileService:
    def __init__(self, *, providers: list[Any], retry_policy: RetryPolicy | None = None) -> None:
        self.providers = providers
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_profiles(self, symbols: list[str]) -> StockProfileResponse:
        normalized, errors = _normalize_symbols(symbols)
        profiles: list[StockProfileData] = []
        provider_name = self.providers[0].name
        provider_status = "ok"
        fallbacks: list[FallbackRecord] = []
        if normalized:
            profiles, provider_name, provider_status, fallbacks = await self._fetch(normalized)
            found = {profile.symbol.display_symbol for profile in profiles}
            for symbol in normalized:
                if symbol.display_symbol not in found:
                    errors.append(
                        StockProfileItemError(
                            symbol=symbol.display_symbol,
                            error=ErrorDetail(
                                type=ErrorType.SYMBOL_NOT_FOUND.value,
                                message="Provider returned no quote data for this symbol.",
                                provider=provider_name,
                                retryable=False,
                            ),
                        )
                    )
        return StockProfileResponse(
            status="ok",
            provider=provider_name,
            provider_status=provider_status,
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=fallbacks,
            data=StockProfilesData(profiles=profiles, errors=errors),
        )

    async def _fetch(
        self,
        normalized: list[NormalizedSymbol],
    ) -> tuple[list[StockProfileData], str, str, list[FallbackRecord]]:
        fallbacks: list[FallbackRecord] = []
        last_error: ProviderError | None = None
        for index, provider in enumerate(self.providers):
            try:
                profiles = await logged_provider_call(
                    operation="stock_profile",
                    provider=provider.name,
                    symbol=normalized[0] if len(normalized) == 1 else None,
                    fallback_count=len(fallbacks),
                    call=lambda provider=provider: run_with_retries(
                        lambda: provider.get_profiles(normalized),
                        policy=self.retry_policy,
                    ),
                )
                return profiles, provider.name, "ok" if not fallbacks else "fallback", fallbacks
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


def _normalize_symbols(
    symbols: list[str],
) -> tuple[list[NormalizedSymbol], list[StockProfileItemError]]:
    # 逐票归一化：格式非法的标的不阻断整批，记入 errors；
    # 合法标的按 display_symbol 去重并保持请求顺序。
    normalized: list[NormalizedSymbol] = []
    errors: list[StockProfileItemError] = []
    seen: set[str] = set()
    for raw in symbols:
        try:
            symbol = normalize_symbol(raw)
        except ProviderError as exc:
            errors.append(
                StockProfileItemError(
                    symbol=raw,
                    error=ErrorDetail(
                        type=exc.error_type.value,
                        message=exc.message,
                        provider=None,
                        retryable=False,
                    ),
                )
            )
            continue
        if symbol.display_symbol in seen:
            continue
        seen.add(symbol.display_symbol)
        normalized.append(symbol)
    return normalized, errors
