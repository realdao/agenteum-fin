from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.errors import ProviderError
from src.utils.symbols import NormalizedSymbol

T = TypeVar("T")

LOGGER = logging.getLogger("agenteum_fin.provider")


async def logged_provider_call(
    *,
    operation: str,
    provider: str,
    symbol: NormalizedSymbol | None,
    fallback_count: int,
    call: Callable[[], Awaitable[T]],
) -> T:
    started = time.perf_counter()
    try:
        result = await call()
    except ProviderError as exc:
        _log(
            logging.WARNING,
            operation=operation,
            provider=provider,
            symbol=symbol,
            latency_ms=_elapsed_ms(started),
            status="error",
            fallback_count=fallback_count,
            error_type=exc.error_type.value,
            http_status=exc.http_status,
        )
        raise
    _log(
        logging.INFO,
        operation=operation,
        provider=provider,
        symbol=symbol,
        latency_ms=_elapsed_ms(started),
        status="ok",
        fallback_count=fallback_count,
    )
    return result


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _log(
    level: int,
    *,
    operation: str,
    provider: str,
    symbol: NormalizedSymbol | None,
    latency_ms: float,
    status: str,
    fallback_count: int,
    error_type: str | None = None,
    http_status: int | None = None,
) -> None:
    # symbol 为 None 表示批量调用（如批量 stock_profile），日志不绑定单一标的。
    extra = {
        "operation": operation,
        "provider": provider,
        "market": symbol.market if symbol else None,
        "symbol": symbol.display_symbol if symbol else None,
        "latency_ms": latency_ms,
        "status": status,
        "fallback_count": fallback_count,
    }
    if error_type is not None:
        extra["error_type"] = error_type
    if http_status is not None:
        extra["http_status"] = http_status
    LOGGER.log(level, "finance provider call", extra=extra)
