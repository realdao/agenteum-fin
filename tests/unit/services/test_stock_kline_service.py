import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest
from src.services.retry import RetryPolicy
from src.services.stock_kline_service import StockKlineService


@pytest.mark.asyncio
async def test_hk_kline_returns_unsupported_market_when_provider_is_none():
    service = StockKlineService(a_share_provider=None, hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


class FakeAshareKlineProvider:
    name = "mootdx"

    def __init__(self, *, error_type=None, failures: int | None = None):
        self.error_type = error_type
        self.failures = failures
        self.calls = 0
        self.requests = []

    async def get_kline(self, symbol, request):
        self.calls += 1
        self.requests.append(request)
        if self.error_type and (self.failures is None or self.calls <= self.failures):
            raise ProviderError(
                error_type=self.error_type,
                provider=self.name,
                message="temporary failure",
            )
        return KlineData(
            symbol=symbol,
            period=request.period,
            adjust=request.adjust,
            bars=[KlineBar(date="2026-05-22", open=1, high=2, low=1, close=2)],
        )


@pytest.mark.asyncio
async def test_a_share_kline_success_uses_configured_provider():
    service = StockKlineService(a_share_provider=FakeAshareKlineProvider(), hk_provider=None)

    response = await service.get_kline(KlineRequest(symbol="600519"))

    assert response.provider == "mootdx"
    assert response.data.bars[0].date == "2026-05-22"


class FakeHkKlineProvider(FakeAshareKlineProvider):
    name = "tencent"


@pytest.mark.asyncio
async def test_hk_kline_success_uses_configured_provider():
    service = StockKlineService(a_share_provider=None, hk_provider=FakeHkKlineProvider())

    response = await service.get_kline(KlineRequest(symbol="00700"))

    assert response.provider == "tencent"
    assert response.data.symbol.market == "hk"
    assert response.data.bars[0].date == "2026-05-22"


@pytest.mark.asyncio
async def test_kline_rejects_unsupported_adjustment_before_provider_call():
    service = StockKlineService(a_share_provider=FakeAshareKlineProvider(), hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="600519", adjust="qfq"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_ADJUSTMENT


@pytest.mark.asyncio
async def test_kline_retries_same_provider_when_configured():
    provider = FakeAshareKlineProvider(error_type=ErrorType.TIMEOUT, failures=1)
    service = StockKlineService(
        a_share_provider=provider,
        hk_provider=None,
        retry_policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    response = await service.get_kline(KlineRequest(symbol="600519"))

    assert response.provider == "mootdx"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_kline_forwards_date_filters_and_limit_to_provider():
    provider = FakeAshareKlineProvider()
    service = StockKlineService(a_share_provider=provider, hk_provider=None)

    await service.get_kline(
        KlineRequest(
            symbol="600519",
            start_date="2026-01-01",
            end_date="2026-05-22",
            limit=10,
        )
    )

    assert provider.requests[0].start_date == "2026-01-01"
    assert provider.requests[0].end_date == "2026-05-22"
    assert provider.requests[0].limit == 10
