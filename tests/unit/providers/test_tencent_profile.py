from pathlib import Path

import httpx
import pytest

from src.providers.profile.tencent import TencentProfileProvider
from src.utils.symbols import normalize_symbol


def fixture_text() -> str:
    return Path("tests/fixtures/tencent_quote.txt").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_tencent_maps_a_share_units():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "q=sh600519" in str(request.url)
        return httpx.Response(200, content=fixture_text().encode("gbk"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TencentProfileProvider(client=client)

    data = await provider.get_profile(normalize_symbol("600519"))

    assert data.name == "贵州茅台"
    assert data.volume == 4_915_700
    assert data.amount == 6_372_390_000
    assert data.turnover_rate == 0.39
    assert data.pe_ttm == 19.53
    assert data.pb == 5.96


@pytest.mark.asyncio
async def test_tencent_maps_hk_fields_without_turnover_rate():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "q=hk00700" in str(request.url)
        return httpx.Response(200, content=fixture_text().encode("gbk"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TencentProfileProvider(client=client)

    data = await provider.get_profile(normalize_symbol("00700"))

    assert data.name == "腾讯控股"
    assert data.volume == 23998219.0
    assert data.amount == 10609807754.648
    assert data.turnover_rate is None
    assert data.pb == 3.16
    assert data.currency == "HKD"
