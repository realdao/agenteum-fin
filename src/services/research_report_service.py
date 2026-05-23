from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import ResearchReportsData, ResearchReportsResponse
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol


class ResearchReportService:
    def __init__(self, *, provider: Any, retry_policy: RetryPolicy | None = None) -> None:
        self.provider = provider
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_reports(self, symbol: str, *, page_size: int) -> ResearchReportsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Research reports are supported for A-shares only in v1.",
            )
        if self.provider is None:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=None,
                message="Research reports provider is not configured.",
            )
        reports = await logged_provider_call(
            operation="stock_research_reports",
            provider=self.provider.name,
            symbol=normalized,
            fallback_count=0,
            call=lambda: run_with_retries(
                lambda: self.provider.get_reports(normalized, page_size),
                policy=self.retry_policy,
            ),
        )
        return ResearchReportsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=ResearchReportsData(symbol=normalized, reports=reports),
        )
