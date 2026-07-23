import sys
import types

import pandas as pd
import pytest
import requests

from src.errors import ErrorType, ProviderError
from src.providers.fundamental.akshare_financials import AkshareFinancialsProvider
from src.utils.symbols import normalize_symbol

SYMBOL = normalize_symbol("600519")


def _install_fake_akshare(monkeypatch, **functions):
    fake = types.ModuleType("akshare")
    for name, func in functions.items():
        setattr(fake, name, func)
    monkeypatch.setitem(sys.modules, "akshare", fake)
    return fake


@pytest.mark.asyncio
async def test_financial_abstract_keeps_first_duplicate_metric_and_period_columns(monkeypatch):
    def stock_financial_abstract(code):
        assert code == "600519"
        return pd.DataFrame(
            {
                "选项": ["常用指标", "常用指标", "成长能力"],
                "指标": ["营业总收入", "归母净利润", "归母净利润"],
                "20260331": [500e8, 260e8, 260e8],
                "20251231": [1700e8, 800e8, 800e8],
                "备注": ["x", "y", "z"],
            }
        )

    _install_fake_akshare(monkeypatch, stock_financial_abstract=stock_financial_abstract)
    provider = AkshareFinancialsProvider()

    abstract = await provider.get_financial_abstract(SYMBOL)

    # 非 8 位数字的列被丢弃；重复指标保留首次出现
    assert set(abstract) == {"营业总收入", "归母净利润"}
    assert abstract["归母净利润"] == {"20260331": 260e8, "20251231": 800e8}


@pytest.mark.asyncio
async def test_sina_reports_convert_nan_to_none_and_keep_period_keys(monkeypatch):
    def stock_financial_report_sina(stock, symbol):
        assert stock == "sh600519"
        if symbol == "资产负债表":
            return pd.DataFrame(
                {
                    "报告日": ["20251231", "20241231"],
                    "资产总计": [3000e8, 2800e8],
                    "商誉": [float("nan"), 1e8],
                }
            )
        return pd.DataFrame({"报告日": ["20251231"], "营业收入": [1690e8]})

    _install_fake_akshare(
        monkeypatch,
        stock_financial_report_sina=stock_financial_report_sina,
    )
    provider = AkshareFinancialsProvider()

    bs_rows = await provider.get_balance_sheet(SYMBOL)
    inc_rows = await provider.get_income_statement(SYMBOL)

    assert bs_rows[0]["报告日"] == "20251231"
    assert bs_rows[0]["商誉"] is None
    assert bs_rows[1]["商誉"] == 1e8
    assert inc_rows == [{"报告日": "20251231", "营业收入": 1690e8}]


@pytest.mark.asyncio
async def test_empty_dataframe_raises_market_closed(monkeypatch):
    _install_fake_akshare(
        monkeypatch,
        stock_financial_abstract=lambda code: pd.DataFrame(),
    )
    provider = AkshareFinancialsProvider()

    with pytest.raises(ProviderError) as raised:
        await provider.get_financial_abstract(SYMBOL)
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_requests_errors_are_classified(monkeypatch):
    _install_fake_akshare(
        monkeypatch,
        stock_financial_abstract=lambda code: (_ for _ in ()).throw(
            requests.exceptions.Timeout("timed out")
        ),
    )
    provider = AkshareFinancialsProvider()

    with pytest.raises(ProviderError) as raised:
        await provider.get_financial_abstract(SYMBOL)
    assert raised.value.error_type == ErrorType.TIMEOUT


@pytest.mark.asyncio
async def test_unexpected_errors_become_provider_error(monkeypatch):
    _install_fake_akshare(
        monkeypatch,
        stock_financial_abstract=lambda code: (_ for _ in ()).throw(ValueError("bad schema")),
    )
    provider = AkshareFinancialsProvider()

    with pytest.raises(ProviderError) as raised:
        await provider.get_financial_abstract(SYMBOL)
    assert raised.value.error_type == ErrorType.PROVIDER_ERROR
    assert "bad schema" in raised.value.message
