import pytest

from src.providers.f10.mootdx_f10 import MootdxF10Provider
from src.utils.symbols import normalize_symbol


class FakeQuotes:
    def __init__(self):
        self.calls = []

    def F10(self, **kwargs):
        self.calls.append(kwargs)
        return "公司概况正文"


@pytest.mark.asyncio
async def test_f10_maps_english_section_to_chinese_name():
    quotes = FakeQuotes()
    provider = MootdxF10Provider(quotes=quotes)

    text = await provider.get_f10(normalize_symbol("600519"), "company_profile")

    assert text == "公司概况正文"
    assert quotes.calls[0]["name"] == "公司概况"
