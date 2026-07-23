import pytest

from src.errors import ErrorType, ProviderError
from src.utils.symbols import normalize_symbol


def test_normalizes_shanghai_a_share_variants():
    assert normalize_symbol("600519").model_dump() == {
        "market": "a_share",
        "exchange": "sh",
        "symbol": "600519",
        "display_symbol": "600519.SH",
    }
    assert normalize_symbol("SH600519").display_symbol == "600519.SH"
    assert normalize_symbol("600519.SH").display_symbol == "600519.SH"


def test_normalizes_shenzhen_and_beijing_a_share():
    assert normalize_symbol("000001").display_symbol == "000001.SZ"
    assert normalize_symbol("300750").display_symbol == "300750.SZ"
    assert normalize_symbol("830799").display_symbol == "830799.BJ"


def test_normalizes_hong_kong_variants():
    assert normalize_symbol("00700").model_dump() == {
        "market": "hk",
        "exchange": "hk",
        "symbol": "00700",
        "display_symbol": "00700.HK",
    }
    assert normalize_symbol("00001").display_symbol == "00001.HK"
    assert normalize_symbol("hk00700").display_symbol == "00700.HK"
    assert normalize_symbol("00700.HK").display_symbol == "00700.HK"


def test_explicit_hk_symbol_is_zero_padded_to_five_digits():
    assert normalize_symbol("700.HK").display_symbol == "00700.HK"
    assert normalize_symbol("HK700").display_symbol == "00700.HK"
    assert normalize_symbol("hk0700").display_symbol == "00700.HK"


def test_rejects_explicit_hk_with_six_digit_symbol():
    with pytest.raises(ProviderError) as raised:
        normalize_symbol("000001.HK")

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
