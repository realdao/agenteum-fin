import json
from pathlib import Path

import httpx
import pytest

from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_cninfo_maps_announcement_fields():
    fixture = json.loads(
        Path("tests/fixtures/cninfo_announcements.json").read_text(encoding="utf-8")
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CninfoAnnouncementProvider(client=client)

    items = await provider.get_announcements(normalize_symbol("600519"), page_size=20)

    assert items[0].title == "2025年年度报告"
    assert items[0].announcement_type == "年度报告"
    assert items[0].url == "https://static.cninfo.com.cn/finalpage/2026-04-25/1210000000.PDF"


@pytest.mark.asyncio
async def test_cninfo_uses_stock_list_org_id_for_non_formula_symbols():
    fixture = json.loads(
        Path("tests/fixtures/cninfo_announcements.json").read_text(encoding="utf-8")
    )
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "stockList": [
                        {
                            "code": "601012",
                            "category": "A股",
                            "orgId": "9900022338",
                            "zwjc": "隆基绿能",
                        }
                    ]
                },
            )
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CninfoAnnouncementProvider(client=client)

    items = await provider.get_announcements(normalize_symbol("601012"), page_size=20)

    post_request = next(request for request in requests if request.method == "POST")
    assert "stock=601012%2C9900022338" in post_request.content.decode()
    assert items[0].title == "2025年年度报告"
