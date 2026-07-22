"""Tencent (web.ifzq.gtimg.cn) K-line provider, wired for Hong Kong stocks.

非官方接口，无 SLA。实测（2026-07-22，hk00700）返回稳定、延迟低，
且与 iwencai 行情数据逐日一致。响应体的 K 线数组键名随复权参数变化
（day / qfqday / hfqday），解析时按周期后缀匹配，不做精确键名假设。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest
from src.utils.symbols import NormalizedSymbol

PERIOD_TO_TENCENT = {
    "day": "day",
    "week": "week",
    "month": "month",
}

# fqkline count 参数的常见稳妥上限；更大区间请用 start_date/end_date 分段。
MAX_BARS_PER_REQUEST = 640
DEFAULT_BARS = 320


class TencentKlineProvider:
    name = "tencent"
    supported_adjustments = {"none", "qfq", "hfq"}
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_kline(self, symbol: NormalizedSymbol, request: KlineRequest) -> KlineData:
        period = PERIOD_TO_TENCENT.get(request.period)
        if period is None:
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_PERIOD,
                provider=self.name,
                message=f"Unsupported K-line period: {request.period}",
            )
        query = self._query_symbol(symbol)
        count = min(request.limit or DEFAULT_BARS, MAX_BARS_PER_REQUEST)
        fq = "" if request.adjust == "none" else request.adjust
        param = ",".join(
            [query, period, request.start_date or "", request.end_date or "", str(count), fq]
        )
        payload = await self._get({"param": param})
        rows = self._extract_rows(payload, query, period)
        bars = _filter_bars(
            [_row_to_bar(row) for row in rows],
            start_date=request.start_date,
            end_date=request.end_date,
        )
        if not bars:
            raise ProviderError(
                error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                provider=self.name,
                message="Tencent returned no K-line bars.",
            )
        return KlineData(symbol=symbol, period=request.period, adjust=request.adjust, bars=bars)

    def _query_symbol(self, symbol: NormalizedSymbol) -> str:
        if symbol.market == "hk":
            return f"hk{symbol.symbol}"
        return f"{symbol.exchange}{symbol.symbol}"

    async def _get(self, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = await self.client.get(
                self.url,
                params=params,
                headers={"User-Agent": "Mozilla/5.0"},
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider=self.name,
                message=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                error_type=ErrorType.NETWORK,
                provider=self.name,
                message=str(exc),
            ) from exc
        if response.status_code >= 500:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_5XX,
                provider=self.name,
                message=f"Tencent kline returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=response.text,
            )
        if response.status_code >= 400:
            raise ProviderError(
                error_type=ErrorType.INVALID_REQUEST,
                provider=self.name,
                message=f"Tencent kline returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=response.text,
            )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message="Tencent kline returned a non-JSON body.",
                payload=response.text,
            ) from exc
        if payload.get("code") != 0:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=self.name,
                message=f"Tencent kline returned code={payload.get('code')}: {payload.get('msg')}",
                payload=response.text,
            )
        return payload

    def _extract_rows(
        self,
        payload: dict[str, Any],
        query: str,
        period: str,
    ) -> list[list[Any]]:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message="Tencent kline payload has no data object.",
                payload=payload,
            )
        entry = data.get(query)
        if not isinstance(entry, dict):
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message=f"Tencent kline payload has no entry for {query}.",
                payload=payload,
            )
        # 键名随复权参数变化：day / qfqday / hfqday（week/month 同理），按后缀匹配。
        rows = next(
            (
                value
                for key, value in entry.items()
                if key.endswith(period) and isinstance(value, list)
            ),
            None,
        )
        if rows is None:
            return []
        return [row for row in rows if isinstance(row, list) and len(row) >= 6]


def _row_to_bar(row: list[Any]) -> KlineBar:
    # 行格式：[date, open, close, high, low, volume, {附加信息}...]
    return KlineBar(
        date=str(row[0])[:10],
        open=_float(row[1]),
        close=_float(row[2]),
        high=_float(row[3]),
        low=_float(row[4]),
        volume=_float(row[5]),
        amount=None,
    )


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
