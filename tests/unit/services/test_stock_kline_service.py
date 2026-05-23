import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import KlineRequest
from src.services.stock_kline_service import StockKlineService


@pytest.mark.asyncio
async def test_hk_kline_returns_unsupported_market_when_provider_is_none():
    service = StockKlineService(a_share_provider=None, hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET
