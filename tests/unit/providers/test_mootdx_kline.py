import pandas as pd
import pytest

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
            "datetime": ["2026-05-22"],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "vol": [1000],
            "amount": [2000],
        }
    )
    frame.index = pd.Index(["2026-05-22"], name="datetime")
    quotes = FakeQuotes(frame)
    provider = MootdxKlineProvider(quotes=quotes)

    data = await provider.get_kline(
        normalize_symbol("600519"),
        KlineRequest(symbol="600519", period="day", limit=1),
    )

    assert quotes.calls[0]["symbol"] == "600519"
    assert quotes.calls[0]["frequency"] == "day"
    assert quotes.calls[0]["offset"] == 1
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
