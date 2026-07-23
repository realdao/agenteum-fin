from __future__ import annotations

import re

from pydantic import BaseModel

from src.errors import ErrorType, ProviderError


class NormalizedSymbol(BaseModel):
    market: str
    exchange: str
    symbol: str
    display_symbol: str


def normalize_symbol(raw: str) -> NormalizedSymbol:
    value = raw.strip().upper()
    explicit_hk = value.startswith("HK") or value.endswith(".HK")
    value = re.sub(r"^(SH|SZ|BJ|HK)", "", value)
    suffix = None
    if "." in value:
        value, suffix = value.split(".", 1)
    if not value.isdigit():
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Invalid stock symbol: {raw}",
        )
    if explicit_hk or suffix == "HK" or len(value) == 5:
        # 显式港股（HK 前缀或 .HK 后缀）时自动补零到 5 位，如 700.HK -> 00700.HK。
        if explicit_hk or suffix == "HK":
            value = value.zfill(5)
        if len(value) != 5:
            raise ProviderError(
                error_type=ErrorType.INVALID_SYMBOL,
                provider=None,
                message="Hong Kong symbols must normalize to five digits.",
            )
        return NormalizedSymbol(
            market="hk",
            exchange="hk",
            symbol=value,
            display_symbol=f"{value}.HK",
        )
    if len(value) != 6:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message="A-share symbols must normalize to six digits.",
        )
    exchange = _a_share_exchange(value)
    if suffix is not None and suffix.lower() != exchange:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Symbol suffix {suffix} does not match inferred exchange {exchange}.",
        )
    return NormalizedSymbol(
        market="a_share",
        exchange=exchange,
        symbol=value,
        display_symbol=f"{value}.{exchange.upper()}",
    )


def _a_share_exchange(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return "sh"
    if symbol.startswith(("0", "2", "3")):
        return "sz"
    if symbol.startswith(("4", "8")):
        return "bj"
    raise ProviderError(
        error_type=ErrorType.INVALID_SYMBOL,
        provider=None,
        message=f"Unsupported A-share prefix: {symbol[0]}",
    )
