import json

import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.market_data.tencent_kline import TencentKlineProvider
from src.schemas import KlineRequest
from src.utils.symbols import normalize_symbol

ROWS = [
    ["2026-07-20", "470.000", "477.800", "480.000", "468.000", "30822839.000", {}],
    ["2026-07-21", "478.000", "474.000", "479.000", "470.000", "21362780.000", {}],
]


def payload(rows=ROWS, *, key="day", code=0, msg=""):
    return json.dumps(
        {"code": code, "msg": msg, "data": {"hk00700": {key: rows}}}
    ).encode()


def make_provider(handler) -> TencentKlineProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TencentKlineProvider(client=client)


@pytest.mark.asyncio
async def test_tencent_hk_kline_maps_rows_in_ascending_order():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "hk00700" in str(request.url)
        assert "day" in str(request.url)
        return httpx.Response(200, content=payload())

    provider = make_provider(handler)
    data = await provider.get_kline(normalize_symbol("00700"), KlineRequest(symbol="00700"))

    assert [bar.date for bar in data.bars] == ["2026-07-20", "2026-07-21"]
    first = data.bars[0]
    assert first.open == 470.0
    assert first.close == 477.8
    assert first.high == 480.0
    assert first.low == 468.0
    assert first.volume == 30822839.0
    assert first.amount is None


@pytest.mark.asyncio
async def test_tencent_hk_kline_matches_adjusted_key_suffix():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "qfq" in str(request.url)
        return httpx.Response(200, content=payload(key="qfqday"))

    provider = make_provider(handler)
    data = await provider.get_kline(
        normalize_symbol("00700"),
        KlineRequest(symbol="00700", adjust="qfq"),
    )

    assert len(data.bars) == 2
    assert data.adjust == "qfq"


@pytest.mark.asyncio
async def test_tencent_hk_kline_rejects_unsupported_period():
    provider = make_provider(lambda request: httpx.Response(200, content=payload()))

    with pytest.raises(ProviderError) as raised:
        await provider.get_kline(
            normalize_symbol("00700"),
            KlineRequest(symbol="00700", period="quarter"),
        )

    assert raised.value.error_type == ErrorType.UNSUPPORTED_PERIOD


@pytest.mark.asyncio
async def test_tencent_hk_kline_raises_empty_when_no_rows():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload(rows=[]))

    provider = make_provider(handler)

    with pytest.raises(ProviderError) as raised:
        await provider.get_kline(normalize_symbol("00700"), KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_tencent_hk_kline_raises_provider_error_on_nonzero_code():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload(code=1, msg="param error"))

    provider = make_provider(handler)

    with pytest.raises(ProviderError) as raised:
        await provider.get_kline(normalize_symbol("00700"), KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_tencent_hk_kline_applies_date_filters():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload())

    provider = make_provider(handler)
    data = await provider.get_kline(
        normalize_symbol("00700"),
        KlineRequest(symbol="00700", start_date="2026-07-21", end_date="2026-07-21"),
    )

    assert [bar.date for bar in data.bars] == ["2026-07-21"]
