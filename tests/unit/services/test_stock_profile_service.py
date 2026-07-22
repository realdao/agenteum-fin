import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import FallbackRecord, StockProfileData
from src.services.retry import RetryPolicy
from src.services.stock_profile_service import StockProfileService
from src.utils.symbols import normalize_symbol


class FakeProfileProvider:
    def __init__(self, name="tencent", *, error_type=None, failures: int | None = None):
        self.name = name
        self.error_type = error_type
        self.failures = failures
        self.calls = 0
        self.requests: list[list] = []

    async def get_profiles(self, symbols):
        self.calls += 1
        self.requests.append(symbols)
        if self.error_type and (self.failures is None or self.calls <= self.failures):
            raise ProviderError(
                error_type=self.error_type,
                provider=self.name,
                message=f"{self.name} failed",
            )
        return [
            StockProfileData(symbol=symbol, name="贵州茅台", price=1290.2) for symbol in symbols
        ]


@pytest.mark.asyncio
async def test_profile_service_normalizes_symbols_before_provider_call():
    service = StockProfileService(providers=[FakeProfileProvider()])

    response = await service.get_profiles(["SH600519", "600519.SH", "00700"])

    assert response.status == "ok"
    assert response.provider == "tencent"
    # 同一只票的不同写法去重为一次 provider 请求。
    assert [p.symbol for p in response.data.profiles] == [
        normalize_symbol("600519"),
        normalize_symbol("00700"),
    ]
    assert response.data.errors == []


@pytest.mark.asyncio
async def test_profile_service_records_invalid_symbols_without_failing_batch():
    service = StockProfileService(providers=[FakeProfileProvider()])

    response = await service.get_profiles(["not-a-symbol", "600519"])

    assert response.status == "ok"
    assert [p.symbol.display_symbol for p in response.data.profiles] == ["600519.SH"]
    assert len(response.data.errors) == 1
    assert response.data.errors[0].symbol == "not-a-symbol"
    assert response.data.errors[0].error.type == "invalid_symbol"


@pytest.mark.asyncio
async def test_profile_service_marks_symbols_missing_from_provider_response():
    class PartialProvider(FakeProfileProvider):
        async def get_profiles(self, symbols):
            return [StockProfileData(symbol=symbols[0], name="贵州茅台")]

    service = StockProfileService(providers=[PartialProvider()])

    response = await service.get_profiles(["600519", "00700"])

    assert [p.symbol.display_symbol for p in response.data.profiles] == ["600519.SH"]
    assert len(response.data.errors) == 1
    assert response.data.errors[0].symbol == "00700.HK"
    assert response.data.errors[0].error.type == "symbol_not_found"


@pytest.mark.asyncio
async def test_profile_service_falls_back_for_recoverable_errors_only():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.TIMEOUT)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    response = await service.get_profiles(["600519"])

    assert response.provider == "fallback"
    assert response.provider_status == "fallback"
    assert response.fallbacks == [
        FallbackRecord(from_provider="primary", to_provider="fallback", reason="timeout")
    ]


@pytest.mark.asyncio
async def test_profile_service_stops_on_non_recoverable_errors():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.AUTH_ERROR)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    with pytest.raises(ProviderError) as raised:
        await service.get_profiles(["600519"])

    assert raised.value.error_type == ErrorType.AUTH_ERROR
    assert second.calls == 0


@pytest.mark.asyncio
async def test_profile_service_retries_same_provider_before_fallback():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.TIMEOUT, failures=1)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(
        providers=[first, second],
        retry_policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    response = await service.get_profiles(["600519"])

    assert response.provider == "primary"
    assert first.calls == 2
    assert second.calls == 0


@pytest.mark.asyncio
async def test_profile_service_attaches_fallbacks_to_exhausted_error():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.TIMEOUT)
    second = FakeProfileProvider(name="fallback", error_type=ErrorType.TIMEOUT)
    service = StockProfileService(providers=[first, second])

    with pytest.raises(ProviderError) as raised:
        await service.get_profiles(["600519"])

    assert raised.value.fallbacks == [
        FallbackRecord(from_provider="primary", to_provider="fallback", reason="timeout")
    ]


@pytest.mark.asyncio
async def test_profile_service_skips_provider_when_all_symbols_invalid():
    provider = FakeProfileProvider()
    service = StockProfileService(providers=[provider])

    response = await service.get_profiles(["bad-symbol"])

    assert provider.calls == 0
    assert response.data.profiles == []
    assert len(response.data.errors) == 1
