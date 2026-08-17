import pytest

from src.errors import ErrorType, ProviderError
from src.services.announcement_service import AnnouncementService


class FakeAnnouncementProvider:
    name = "cninfo"

    async def get_announcements(self, symbol, page_size):
        return []


@pytest.mark.asyncio
async def test_announcement_service_rejects_hk_symbols():
    service = AnnouncementService(provider=FakeAnnouncementProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_announcements("00700", page_size=20)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["561360", "159870", "399365"])
async def test_announcement_service_rejects_fund_and_index_with_routing_hint(raw):
    service = AnnouncementService(provider=FakeAnnouncementProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_announcements(raw, page_size=20)

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert "iwencai" in raised.value.message


@pytest.mark.asyncio
async def test_announcement_service_returns_a_share_response():
    service = AnnouncementService(provider=FakeAnnouncementProvider())

    response = await service.get_announcements("600519", page_size=20)

    assert response.provider == "cninfo"
    assert response.data.symbol.display_symbol == "600519.SH"


@pytest.mark.asyncio
async def test_announcement_service_rejects_unconfigured_provider():
    service = AnnouncementService(provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_announcements("600519", page_size=20)

    assert raised.value.error_type == ErrorType.CONFIG_ERROR
