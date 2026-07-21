from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from src.errors import ErrorType, ProviderError

T = TypeVar("T")

RETRYABLE_ERROR_TYPES = {
    ErrorType.TIMEOUT,
    ErrorType.NETWORK,
    ErrorType.PROVIDER_5XX,
}


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 1
    backoff_seconds: float = 0.5

    @classmethod
    def from_settings(cls, settings) -> RetryPolicy:
        return cls(
            attempts=max(1, int(settings.fin_retry_attempts)),
            backoff_seconds=max(0.0, float(settings.fin_retry_backoff_seconds)),
        )


async def run_with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
) -> T:
    return await run_with_retries_indexed(lambda attempt: operation(), policy=policy)


async def run_with_retries_indexed(
    operation: Callable[[int], Awaitable[T]],
    *,
    policy: RetryPolicy,
) -> T:
    """Like run_with_retries, but the operation receives the 1-based attempt number.

    Lets callers vary behavior per attempt (e.g. mark retries on the wire)
    while keeping the same retryable-error and backoff semantics.
    """
    attempts = max(1, policy.attempts)
    for attempt in range(1, attempts + 1):
        try:
            return await operation(attempt)
        except ProviderError as exc:
            if exc.error_type not in RETRYABLE_ERROR_TYPES or attempt >= attempts:
                raise
            if policy.backoff_seconds:
                await asyncio.sleep(policy.backoff_seconds)
    raise RuntimeError("unreachable retry state")
