from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import F10Data, F10Response
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol

SECTION_LABELS = {
    "company_profile": "公司概况",
    "latest_notice": "最新提示",
    "shareholders": "股东研究",
    "capital_structure": "股本结构",
    "financial_analysis": "财务分析",
}


class StockF10Service:
    def __init__(self, *, provider: Any, retry_policy: RetryPolicy | None = None) -> None:
        self.provider = provider
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_f10(self, symbol: str, *, section: str, max_chars: int) -> F10Response:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="F10 is supported for A-shares only in v1.",
            )
        if self.provider is None:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=None,
                message="F10 provider is not configured.",
            )
        text = await logged_provider_call(
            operation=f"stock_f10.{section}",
            provider=self.provider.name,
            symbol=normalized,
            fallback_count=0,
            call=lambda: run_with_retries(
                lambda: self.provider.get_f10(normalized, section),
                policy=self.retry_policy,
            ),
        )
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
                provider_section=SECTION_LABELS[section],
                text=text[:max_chars],
                truncated=truncated,
            ),
        )
