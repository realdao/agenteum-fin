import json
from pathlib import Path

import httpx
import pytest

from src.providers.research.eastmoney import EastmoneyResearchReportProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_eastmoney_maps_research_report_fields():
    fixture = json.loads(
        Path("tests/fixtures/eastmoney_research_reports.json").read_text(encoding="utf-8")
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params)["code"] == "600519"
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = EastmoneyResearchReportProvider(client=client)

    reports = await provider.get_reports(normalize_symbol("600519"), page_size=20)

    assert reports[0].title == "公司深度报告"
    assert reports[0].institution == "示例证券"
    assert reports[0].eps_forecast["predict_this_year_eps"] == "50.1"
    assert reports[0].pdf_url == "https://pdf.dfcfw.com/pdf/H3_AP202605220000001_1.pdf"
