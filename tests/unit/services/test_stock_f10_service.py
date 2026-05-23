import pytest

from src.errors import ErrorType, ProviderError
from src.services.stock_f10_service import StockF10Service


class FakeF10Provider:
    name = "mootdx"

    async def get_f10(self, symbol, section):
        return "x" * 20


@pytest.mark.asyncio
async def test_f10_service_rejects_hk_symbols():
    service = StockF10Service(provider=FakeF10Provider())

    with pytest.raises(ProviderError) as raised:
        await service.get_f10("00700", section="company_profile", max_chars=10)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_f10_service_truncates_long_text():
    service = StockF10Service(provider=FakeF10Provider())

    response = await service.get_f10("600519", section="company_profile", max_chars=10)

    assert response.data.text == "x" * 10
    assert response.data.truncated is True
    assert response.data.provider_section == "公司概况"


@pytest.mark.asyncio
async def test_f10_service_rejects_unconfigured_provider():
    service = StockF10Service(provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_f10("600519", section="company_profile", max_chars=10)

    assert raised.value.error_type == ErrorType.CONFIG_ERROR
