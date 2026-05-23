import pandas as pd
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.schemas import KlineRequest
from src.utils.symbols import normalize_symbol


class FakeQuotes:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def bars(self, **kwargs):
        self.calls.append(kwargs)
        return self.frame


@pytest.mark.asyncio
async def test_mootdx_provider_maps_daily_bars_and_drops_duplicate_datetime_column():
    frame = pd.DataFrame(
        {
            "datetime": ["2026-05-19", "2026-05-22"],
            "open": [0.8, 1.0],
            "high": [0.9, 2.0],
            "low": [0.7, 0.5],
            "close": [0.85, 1.5],
            "vol": [500, 1000],
            "amount": [1000, 2000],
        }
    )
    frame.index = pd.Index(["2026-05-19", "2026-05-22"], name="datetime")
    quotes = FakeQuotes(frame)
    provider = MootdxKlineProvider(quotes=quotes)

    data = await provider.get_kline(
        normalize_symbol("600519"),
        KlineRequest(
            symbol="600519",
            period="day",
            start_date="2026-05-20",
            end_date="2026-05-22",
            limit=1,
        ),
    )

    assert quotes.calls[0]["symbol"] == "600519"
    assert quotes.calls[0]["frequency"] == "day"
    assert quotes.calls[0]["offset"] == 1
    assert "start" not in quotes.calls[0]
    assert "end" not in quotes.calls[0]
    assert len(data.bars) == 1
    assert data.bars[0].date == "2026-05-22"
    assert data.bars[0].volume == 1000


@pytest.mark.asyncio
async def test_mootdx_provider_supports_quarter_as_three_month_frequency():
    frame = pd.DataFrame(
        {"datetime": ["2026-03-31"], "open": [1], "high": [1], "low": [1], "close": [1]}
    )
    quotes = FakeQuotes(frame)
    provider = MootdxKlineProvider(quotes=quotes)

    await provider.get_kline(
        normalize_symbol("600519"),
        KlineRequest(symbol="600519", period="quarter"),
    )

    assert quotes.calls[0]["frequency"] == "3mon"


@pytest.mark.asyncio
async def test_mootdx_provider_rejects_unknown_period_with_provider_error():
    provider = MootdxKlineProvider(quotes=FakeQuotes(pd.DataFrame()))
    request = KlineRequest.model_construct(symbol="600519", period="minute")

    with pytest.raises(ProviderError) as raised:
        await provider.get_kline(normalize_symbol("600519"), request)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_PERIOD
