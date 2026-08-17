import pytest

from src.errors import ErrorType, ProviderError
from src.utils.symbols import normalize_symbol, require_stock_symbol


def test_normalizes_shanghai_a_share_variants():
    assert normalize_symbol("600519").model_dump() == {
        "market": "a_share",
        "exchange": "sh",
        "symbol": "600519",
        "display_symbol": "600519.SH",
        "asset_type": "stock",
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
        "asset_type": "stock",
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


# ---------------------------------------------------------------- fund/index


@pytest.mark.parametrize(
    ("raw", "exchange"),
    [
        ("561360", "sh"),
        ("510300", "sh"),
        ("500001", "sh"),
        ("SH501000", "sh"),
        ("159870", "sz"),
        ("162411", "sz"),
        ("159698", "sz"),
    ],
)
def test_normalizes_fund_symbols_across_exchanges(raw, exchange):
    symbol = normalize_symbol(raw)

    assert symbol.market == "a_share"
    assert symbol.exchange == exchange
    assert symbol.asset_type == "fund"


def test_fund_examples_map_to_expected_exchanges():
    assert normalize_symbol("561360").display_symbol == "561360.SH"
    assert normalize_symbol("159870").display_symbol == "159870.SZ"


def test_fund_symbol_with_conflicting_exchange_suffix_is_rejected():
    with pytest.raises(ProviderError) as raised:
        normalize_symbol("561360.SZ")

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert "does not match inferred exchange" in raised.value.message


@pytest.mark.parametrize("raw", ["399365", "399001", "399365.SZ", "SZ399365"])
def test_normalizes_sz_index_symbols(raw):
    symbol = normalize_symbol(raw)

    assert symbol.market == "a_share"
    assert symbol.exchange == "sz"
    assert symbol.asset_type == "index"
    assert symbol.display_symbol.startswith("399")


@pytest.mark.parametrize("raw", ["000001.SH", "000300.SH", "sh000300", "SH000001"])
def test_normalizes_sh_index_symbols_only_with_explicit_exchange(raw):
    symbol = normalize_symbol(raw)

    assert symbol.market == "a_share"
    assert symbol.exchange == "sh"
    assert symbol.asset_type == "index"
    assert symbol.symbol.startswith("000")


def test_bare_000xxx_stays_shenzhen_stock_for_backward_compatibility():
    symbol = normalize_symbol("000001")

    assert symbol.market == "a_share"
    assert symbol.exchange == "sz"
    assert symbol.asset_type == "stock"
    assert symbol.display_symbol == "000001.SZ"


def test_convertible_bond_prefixes_are_rejected_with_hint():
    for raw in ("113050", "110059", "123456", "128100"):
        with pytest.raises(ProviderError) as raised:
            normalize_symbol(raw)

        assert raised.value.error_type == ErrorType.INVALID_SYMBOL
        assert "可转债" in raised.value.message


def test_require_stock_symbol_rejects_fund_with_routing_hint():
    with pytest.raises(ProviderError) as raised:
        require_stock_symbol(normalize_symbol("159870"))

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert "stock_kline" in raised.value.message
    assert "iwencai_query" in raised.value.message


def test_require_stock_symbol_rejects_index_with_routing_hint():
    with pytest.raises(ProviderError) as raised:
        require_stock_symbol(normalize_symbol("399365"))

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert "stock_kline" in raised.value.message
    assert "iwencai_query" in raised.value.message


def test_require_stock_symbol_accepts_stocks():
    require_stock_symbol(normalize_symbol("600519"))
    require_stock_symbol(normalize_symbol("00700"))
