"""akshare 财务数据源（stock_fundamental_snapshot 的财务摘要与新浪报表来源）。

移植自 workspace 技能 company-fundamental-analysis 的取数层：

- `stock_financial_abstract`：同花顺财务摘要，按报告期给出营业总收入/归母/扣非/
  净资产/经营现金流/商誉等关键指标（扣非净利润的唯一稳定来源）。
- `stock_financial_report_sina`：新浪财经资产负债表/利润表，中文科目列。

akshare 是同步 requests 实现，统一用 `asyncio.to_thread` 包装为异步接口；
akshare 在模块级 import 时开销较大，因此在使用时才惰性导入。
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pandas as pd
import requests

from src.errors import ErrorType, ProviderError
from src.utils.symbols import NormalizedSymbol

_PERIOD_PATTERN = re.compile(r"\d{8}")


class AkshareFinancialsProvider:
    name = "akshare"

    async def get_financial_abstract(
        self,
        symbol: NormalizedSymbol,
    ) -> dict[str, dict[str, Any]]:
        """返回 {指标名: {期间(YYYYMMDD): 原始值}}；同名指标跨分类重复时保留首次出现。"""
        df = await self._run(lambda ak: ak.stock_financial_abstract(symbol.symbol))
        if df is None or df.empty:
            raise _empty(self.name, "financial abstract")
        indexed = df.set_index("指标")
        periods = [c for c in indexed.columns if _PERIOD_PATTERN.fullmatch(str(c))]
        abstract: dict[str, dict[str, Any]] = {}
        for name, row in indexed.iterrows():
            key = str(name)
            if key in abstract:
                continue
            abstract[key] = {str(period): _scalar(row.get(period)) for period in periods}
        return abstract

    async def get_balance_sheet(self, symbol: NormalizedSymbol) -> list[dict[str, Any]]:
        return await self._sina_report(symbol, "资产负债表")

    async def get_income_statement(self, symbol: NormalizedSymbol) -> list[dict[str, Any]]:
        return await self._sina_report(symbol, "利润表")

    async def _sina_report(
        self,
        symbol: NormalizedSymbol,
        report_name: str,
    ) -> list[dict[str, Any]]:
        stock = f"{symbol.exchange}{symbol.symbol}"
        df = await self._run(
            lambda ak: ak.stock_financial_report_sina(stock=stock, symbol=report_name)
        )
        if df is None or df.empty:
            raise _empty(self.name, f"sina {report_name}")
        return [
            {str(key): _scalar(value) for key, value in row.items()}
            for row in df.to_dict("records")
        ]

    async def _run(self, work: Callable[[Any], Any]) -> Any:
        try:
            import akshare as ak
        except ImportError as exc:  # pragma: no cover - akshare 是声明依赖
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider=self.name,
                message="akshare is not installed; run 'uv sync'.",
            ) from exc
        try:
            return await asyncio.to_thread(work, ak)
        except Exception as exc:
            raise _classify(exc, self.name) from exc


def _empty(provider: str, what: str) -> ProviderError:
    return ProviderError(
        error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
        provider=provider,
        message=f"akshare returned an empty {what}.",
    )


def _classify(exc: Exception, provider: str) -> ProviderError:
    if isinstance(exc, requests.exceptions.Timeout):
        return ProviderError(
            error_type=ErrorType.TIMEOUT,
            provider=provider,
            message=str(exc),
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return ProviderError(
            error_type=ErrorType.NETWORK,
            provider=provider,
            message=str(exc),
        )
    return ProviderError(
        error_type=ErrorType.PROVIDER_ERROR,
        provider=provider,
        message=str(exc)[:300],
    )


def _scalar(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001 - numpy 标量转换失败时保留原值
            pass
    return value
