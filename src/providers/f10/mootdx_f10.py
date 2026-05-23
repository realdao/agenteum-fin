from __future__ import annotations

import asyncio
from typing import Any

from src.errors import ErrorType, ProviderError
from src.utils.symbols import NormalizedSymbol

SECTION_MAP = {
    "company_profile": "公司概况",
    "latest_notice": "最新提示",
    "shareholders": "股东研究",
    "capital_structure": "股本结构",
    "financial_analysis": "财务分析",
}


class MootdxF10Provider:
    name = "mootdx"

    def __init__(self, *, quotes: Any | None = None) -> None:
        self.quotes = quotes

    def _quotes(self) -> Any:
        if self.quotes is not None:
            return self.quotes
        try:
            from mootdx.quotes import Quotes
        except ImportError as exc:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider=self.name,
                message=(
                    "mootdx is not installed. Install a verified mootdx wheel separately "
                    "to enable live F10 data."
                ),
            ) from exc
        self.quotes = Quotes.factory(market="std")
        return self.quotes

    async def get_f10(self, symbol: NormalizedSymbol, section: str) -> str:
        provider_section = SECTION_MAP[section]
        try:
            text = await asyncio.to_thread(
                self._quotes().F10,
                symbol=symbol.symbol,
                name=provider_section,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=self.name,
                message=str(exc),
            ) from exc
        return text or ""
