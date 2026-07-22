from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest
from src.utils.symbols import NormalizedSymbol

PERIOD_TO_MOOTDX_FREQUENCY = {
    "day": "day",
    "week": "week",
    "month": "mon",
    "quarter": "3mon",
    "year": "year",
}


class MootdxKlineProvider:
    name = "mootdx"
    supported_adjustments = {"none"}

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
                    "mootdx is not installed. It is a declared project dependency; "
                    "run 'uv sync' to install it and enable live A-share K-line data."
                ),
            ) from exc
        self.quotes = Quotes.factory(market="std")
        return self.quotes

    async def get_kline(self, symbol: NormalizedSymbol, request: KlineRequest) -> KlineData:
        if request.period not in PERIOD_TO_MOOTDX_FREQUENCY:
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_PERIOD,
                provider=self.name,
                message=f"Unsupported K-line period: {request.period}",
            )
        frequency = PERIOD_TO_MOOTDX_FREQUENCY[request.period]
        offset = request.limit or 800
        try:
            frame = await asyncio.to_thread(
                self._quotes().bars,
                symbol=symbol.symbol,
                frequency=frequency,
                offset=offset,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=self.name,
                message=str(exc),
            ) from exc
        bars = _filter_bars(
            _frame_to_bars(frame),
            start_date=request.start_date,
            end_date=request.end_date,
        )
        if not bars:
            raise ProviderError(
                error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                provider=self.name,
                message="mootdx returned no K-line bars.",
            )
        return KlineData(symbol=symbol, period=request.period, adjust=request.adjust, bars=bars)


def _frame_to_bars(frame: pd.DataFrame | None) -> list[KlineBar]:
    if frame is None or frame.empty:
        return []
    normalized = frame.copy()
    if "datetime" in normalized.columns and normalized.index.name == "datetime":
        normalized = normalized.drop(columns=["datetime"])
    normalized = normalized.reset_index()
    bars: list[KlineBar] = []
    for row in normalized.to_dict("records"):
        date_value = row.get("datetime") or row.get("date")
        bars.append(
            KlineBar(
                date=str(date_value)[:10],
                open=_float(row.get("open")),
                high=_float(row.get("high")),
                low=_float(row.get("low")),
                close=_float(row.get("close")),
                volume=_float(row.get("vol") if row.get("vol") is not None else row.get("volume")),
                amount=_float(row.get("amount")),
            )
        )
    return bars


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _filter_bars(
    bars: list[KlineBar],
    *,
    start_date: str | None,
    end_date: str | None,
) -> list[KlineBar]:
    return [
        bar
        for bar in bars
        if (start_date is None or bar.date >= start_date)
        and (end_date is None or bar.date <= end_date)
    ]
