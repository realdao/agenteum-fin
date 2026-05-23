import pytest

from src.errors import ErrorType, ProviderError
from src.services.retry import RetryPolicy, run_with_retries


class FlakyOperation:
    def __init__(self, *, failures: int, error_type: ErrorType = ErrorType.TIMEOUT) -> None:
        self.failures = failures
        self.error_type = error_type
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError(
                error_type=self.error_type,
                provider="fake",
                message="temporary failure",
            )
        return "ok"


@pytest.mark.asyncio
async def test_retry_policy_retries_timeout_when_attempts_greater_than_one():
    operation = FlakyOperation(failures=1)

    result = await run_with_retries(
        operation,
        policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    assert result == "ok"
    assert operation.calls == 2


@pytest.mark.asyncio
async def test_retry_policy_does_not_retry_auth_errors():
    operation = FlakyOperation(failures=1, error_type=ErrorType.AUTH_ERROR)

    with pytest.raises(ProviderError) as raised:
        await run_with_retries(
            operation,
            policy=RetryPolicy(attempts=3, backoff_seconds=0),
        )

    assert raised.value.error_type == ErrorType.AUTH_ERROR
    assert operation.calls == 1
