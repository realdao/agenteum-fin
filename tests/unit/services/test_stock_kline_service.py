import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest
from src.services.stock_kline_service import StockKlineService


@pytest.mark.asyncio
async def test_hk_kline_returns_unsupported_market_when_provider_is_none():
    service = StockKlineService(a_share_provider=None, hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


class FakeAshareKlineProvider:
    name = "mootdx"

    async def get_kline(self, symbol, request):
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


@pytest.mark.asyncio
async def test_kline_rejects_unsupported_adjustment_before_provider_call():
    service = StockKlineService(a_share_provider=FakeAshareKlineProvider(), hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="600519", adjust="qfq"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_ADJUSTMENT
