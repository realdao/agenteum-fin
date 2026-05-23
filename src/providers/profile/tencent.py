from __future__ import annotations

import re

import httpx

from src.errors import ErrorType, ProviderError
from src.schemas import StockProfileData
from src.utils.symbols import NormalizedSymbol


class TencentProfileProvider:
    name = "tencent"
    url = "https://qt.gtimg.cn/q={query}"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_profile(self, symbol: NormalizedSymbol) -> StockProfileData:
        query = self._query_symbol(symbol)
        try:
            response = await self.client.get(
                self.url.format(query=query),
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
                message=f"Tencent quote returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=response.text,
            )
        if response.status_code >= 400:
            raise ProviderError(
                error_type=ErrorType.INVALID_REQUEST,
                provider=self.name,
                message=f"Tencent quote returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=response.text,
            )
        text = response.content.decode("gbk", errors="replace")
        values = self._values_for_query(text, query)
        if symbol.market == "hk":
            return self._map_hk(symbol, values)
        return self._map_a_share(symbol, values)

    def _query_symbol(self, symbol: NormalizedSymbol) -> str:
        if symbol.market == "hk":
            return f"hk{symbol.symbol}"
        return f"{symbol.exchange}{symbol.symbol}"

    def _values_for_query(self, text: str, query: str) -> list[str]:
        pattern = rf"v_{re.escape(query)}=\"([^\"]*)\""
        match = re.search(pattern, text)
        if match is None:
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message=f"Tencent quote did not contain {query}.",
                payload=text,
            )
        values = match.group(1).split("~")
        if len(values) < 53:
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message=f"Tencent quote returned too few fields: {len(values)}.",
                payload=values,
            )
        return values

    def _map_a_share(self, symbol: NormalizedSymbol, values: list[str]) -> StockProfileData:
        return StockProfileData(
            symbol=symbol,
            name=_str(values, 1),
            market=symbol.market,
            exchange=symbol.exchange,
            price=_float(values, 3),
            last_close=_float(values, 4),
            change_amount=_float(values, 31),
            change_percent=_float(values, 32),
            high=_float(values, 33),
            low=_float(values, 34),
            volume=_scale(_float(values, 36), 100),
            amount=_scale(_float(values, 37), 10000),
            turnover_rate=_float(values, 38),
            pe_ttm=_float(values, 39),
            pe_static=_float(values, 52),
            pb=_float(values, 46),
            market_cap=_scale(_float(values, 44), 100000000),
            float_market_cap=_scale(_float(values, 45), 100000000),
            currency="CNY",
        )

    def _map_hk(self, symbol: NormalizedSymbol, values: list[str]) -> StockProfileData:
        return StockProfileData(
            symbol=symbol,
            name=_str(values, 1),
            market=symbol.market,
            exchange=symbol.exchange,
            price=_float(values, 3),
            last_close=_float(values, 4),
            change_amount=_float(values, 31),
            change_percent=_float(values, 32),
            high=_float(values, 33),
            low=_float(values, 34),
            volume=_float(values, 29),
            amount=_null_if_zero(_float(values, 37)),
            turnover_rate=None,
            pe_ttm=_float(values, 39),
            pb=None,
            market_cap=_scale(_float(values, 44), 100000000),
            float_market_cap=_scale(_float(values, 45), 100000000),
            currency=_str(values, 75),
        )


def _str(values: list[str], index: int) -> str | None:
    if index >= len(values):
        return None
    value = values[index].strip()
    return value or None


def _float(values: list[str], index: int) -> float | None:
    value = _str(values, index)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _scale(value: float | None, factor: float) -> float | None:
    if value is None:
        return None
    return value * factor


def _null_if_zero(value: float | None) -> float | None:
    if value in (None, 0):
        return None
    return value
