import pytest

from src.errors import ErrorType, ProviderError
from src.services.research_report_service import ResearchReportService


class FakeResearchProvider:
    name = "eastmoney"

    async def get_reports(self, symbol, page_size):
        return []


@pytest.mark.asyncio
async def test_research_report_service_rejects_hk_symbols():
    service = ResearchReportService(provider=FakeResearchProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_reports("00700", page_size=20)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_research_report_service_returns_a_share_response():
    service = ResearchReportService(provider=FakeResearchProvider())

    response = await service.get_reports("600519", page_size=20)

    assert response.provider == "eastmoney"
    assert response.data.symbol.display_symbol == "600519.SH"
