from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import ResearchReportsData, ResearchReportsResponse
from src.utils.symbols import normalize_symbol


class ResearchReportService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_reports(self, symbol: str, *, page_size: int) -> ResearchReportsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Research reports are supported for A-shares only in v1.",
            )
        reports = await self.provider.get_reports(normalized, page_size)
        return ResearchReportsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=ResearchReportsData(symbol=normalized, reports=reports),
        )
