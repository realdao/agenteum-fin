import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import FallbackRecord, StockProfileData
from src.services.stock_profile_service import StockProfileService
from src.utils.symbols import normalize_symbol


class FakeProfileProvider:
    def __init__(self, name="tencent", *, error_type=None):
        self.name = name
        self.error_type = error_type
        self.calls = 0

    async def get_profile(self, symbol):
        self.calls += 1
        if self.error_type:
            raise ProviderError(
                error_type=self.error_type,
                provider=self.name,
                message=f"{self.name} failed",
            )
        return StockProfileData(symbol=symbol, name="贵州茅台", price=1290.2)


@pytest.mark.asyncio
async def test_profile_service_normalizes_symbol_before_provider_call():
    service = StockProfileService(providers=[FakeProfileProvider()])

    response = await service.get_profile("SH600519")

    assert response.status == "ok"
    assert response.provider == "tencent"
    assert response.data.symbol == normalize_symbol("600519")


@pytest.mark.asyncio
async def test_profile_service_falls_back_for_recoverable_errors_only():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.TIMEOUT)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    response = await service.get_profile("600519")

    assert response.provider == "fallback"
    assert response.fallbacks == [
        FallbackRecord(from_provider="primary", to_provider="fallback", reason="timeout")
    ]


@pytest.mark.asyncio
async def test_profile_service_stops_on_non_recoverable_errors():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.AUTH_ERROR)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    with pytest.raises(ProviderError) as raised:
        await service.get_profile("600519")

    assert raised.value.error_type == ErrorType.AUTH_ERROR
    assert second.calls == 0
