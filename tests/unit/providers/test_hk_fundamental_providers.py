"""港股 provider 方法测试：akshare 东财港股接口包装 + 东财 datacenter RPT_HKF10_*。"""

import sys
import types

import httpx
import pandas as pd
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.fundamental.akshare_financials import AkshareFinancialsProvider
from src.providers.fundamental.eastmoney import EastmoneyFundamentalProvider
from src.utils.symbols import normalize_symbol

HK = normalize_symbol("00700.HK")


def _install_fake_akshare(monkeypatch, **functions):
    fake = types.ModuleType("akshare")
    for name, func in functions.items():
        setattr(fake, name, func)
    monkeypatch.setitem(sys.modules, "akshare", fake)
    return fake


# ---------------------------------------------------------------- akshare 港股


@pytest.mark.asyncio
async def test_hk_company_info_merges_company_and_security_profiles(monkeypatch):
    _install_fake_akshare(
        monkeypatch,
        stock_hk_company_profile_em=lambda symbol: pd.DataFrame(
            [
                {
                    "公司名称": "腾讯控股有限公司",
                    "所属行业": "软件服务",
                    "董事长": "马化腾",
                    "公司秘书": "刘淑仪",
                    "员工人数": "87412",
                    "注册地址": "Cayman Islands",
                    "办公地址": "香港湾仔",
                    "公司网址": "www.tencent.com",
                    "E-MAIL": "ir@tencent.com",
                    "核数师": "罗兵咸永道会计师事务所",
                    "公司介绍": "腾讯是一家互联网科技公司。",
                    "公司成立日期": "1999-11-23",
                }
            ]
        ),
        stock_hk_security_profile_em=lambda symbol: pd.DataFrame(
            [
                {
                    "证券简称": "腾讯控股",
                    "上市日期": "2004-06-16 00:00:00",
                    "交易所": "香港交易所",
                    "板块": "主板",
                }
            ]
        ),
    )
    provider = AkshareFinancialsProvider()

    info = await provider.get_hk_company_info(HK)

    assert info.name == "腾讯控股"
    assert info.full_name == "腾讯控股有限公司"
    assert info.industry == "软件服务"
    assert info.employees == 87412
    assert info.founded_date == "1999-11-23"
    assert info.listing_date == "2004-06-16"
    assert info.exchange == "香港交易所"


@pytest.mark.asyncio
async def test_hk_company_info_raises_when_both_sources_empty(monkeypatch):
    _install_fake_akshare(
        monkeypatch,
        stock_hk_company_profile_em=lambda symbol: pd.DataFrame(),
        stock_hk_security_profile_em=lambda symbol: pd.DataFrame(),
    )
    provider = AkshareFinancialsProvider()

    with pytest.raises(ProviderError) as raised:
        await provider.get_hk_company_info(HK)
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_hk_main_indicators_selects_indicator_param(monkeypatch):
    calls = []

    def stock_financial_hk_analysis_indicator_em(symbol, indicator):
        calls.append((symbol, indicator))
        return pd.DataFrame(
            [{"REPORT_DATE": "2025-12-31 00:00:00", "OPERATE_INCOME": 7500e8, "ROE_AVG": 21.13}]
        )

    _install_fake_akshare(
        monkeypatch,
        stock_financial_hk_analysis_indicator_em=stock_financial_hk_analysis_indicator_em,
    )
    provider = AkshareFinancialsProvider()

    annual = await provider.get_hk_main_indicators_annual(HK)
    report = await provider.get_hk_main_indicators_report(HK)

    assert calls == [("00700", "年度"), ("00700", "报告期")]
    assert annual[0]["OPERATE_INCOME"] == 7500e8
    assert report[0]["ROE_AVG"] == 21.13


@pytest.mark.asyncio
async def test_hk_statements_return_long_format_records(monkeypatch):
    def stock_financial_hk_report_em(stock, symbol, indicator):
        assert stock == "00700"
        return pd.DataFrame(
            [
                {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "总资产", "AMOUNT": 19000e8},
                {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "商誉", "AMOUNT": float("nan")},
            ]
        )

    _install_fake_akshare(
        monkeypatch,
        stock_financial_hk_report_em=stock_financial_hk_report_em,
    )
    provider = AkshareFinancialsProvider()

    rows = await provider.get_hk_balance_sheet_annual(HK)
    assert rows == [
        {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "总资产", "AMOUNT": 19000e8},
        {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "商誉", "AMOUNT": None},
    ]
    rows = await provider.get_hk_balance_sheet_report(HK)
    assert rows[0]["STD_ITEM_NAME"] == "总资产"
    rows = await provider.get_hk_cash_flow_annual(HK)
    assert len(rows) == 2
    rows = await provider.get_hk_income_statement_annual(HK)
    assert len(rows) == 2


# ------------------------------------------------------------- eastmoney 港股


def _em_provider(handler) -> EastmoneyFundamentalProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return EastmoneyFundamentalProvider(client=client)


def _hk_route(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "RPT_HKF10_INFO_EQUITYSTR" in url:
        return httpx.Response(
            200,
            json={
                "result": {
                    "data": [
                        {
                            "CHANGE_DATE": "2026-07-08 00:00:00",
                            "SHARES_TYPE_CODE": "001",
                            "SHARES_TYPE": "已发行普通股",
                            "SHARES_NUM": 9092516289,
                            "SHARES_RATIO": 100,
                        },
                        {
                            "CHANGE_DATE": "2026-07-08 00:00:00",
                            "SHARES_TYPE_CODE": "001001",
                            "SHARES_TYPE": "香港普通股",
                            "SHARES_NUM": 9092516289,
                            "SHARES_RATIO": 100,
                        },
                    ]
                }
            },
        )
    if "RPT_HKF10_EQUITYCHG_HOLDER" in url:
        return httpx.Response(
            200,
            json={
                "result": {
                    "data": [
                        {
                            "REPORT_DATE": "2025-12-31 00:00:00",
                            "HOLDER_NAME": "马化腾",
                            "TOTAL_SHARES": 804859700,
                            "TOTAL_SHARES_RATIO": 8.825,
                            "EQUITY_TYPE": "董事",
                        },
                        {
                            "REPORT_DATE": "2025-12-31 00:00:00",
                            "HOLDER_NAME": "MIH Internet Holdings B.V.",
                            "TOTAL_SHARES": 2079512000,
                            "TOTAL_SHARES_RATIO": 22.8011,
                            "EQUITY_TYPE": "股东",
                        },
                        {
                            "REPORT_DATE": "2025-06-30 00:00:00",
                            "HOLDER_NAME": "上期股东",
                            "TOTAL_SHARES": 100,
                            "TOTAL_SHARES_RATIO": 99.9,
                            "EQUITY_TYPE": "股东",
                        },
                    ]
                }
            },
        )
    return httpx.Response(404, text="not found")


@pytest.mark.asyncio
async def test_hk_share_structure_uses_total_row_without_double_counting():
    # 总计行(001)与构成明细行(001001)数值相同时不可取和
    structure = await _em_provider(_hk_route).get_hk_share_structure(HK)

    assert structure.total_shares == 9092516289


@pytest.mark.asyncio
async def test_hk_share_structure_falls_back_to_max_when_total_row_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "data": [
                        {
                            "CHANGE_DATE": "2026-07-08 00:00:00",
                            "SHARES_TYPE_CODE": "001001",
                            "SHARES_NUM": 21396944434,
                            "SHARES_RATIO": 82.8,
                        },
                        {
                            "CHANGE_DATE": "2026-07-08 00:00:00",
                            "SHARES_TYPE_CODE": "001002",
                            "SHARES_NUM": 4443616133,
                            "SHARES_RATIO": 17.2,
                        },
                    ]
                }
            },
        )

    structure = await _em_provider(handler).get_hk_share_structure(HK)

    assert structure.total_shares == 21396944434


@pytest.mark.asyncio
async def test_hk_major_holders_uses_latest_period_and_sorts_by_ratio():
    holders = await _em_provider(_hk_route).get_hk_major_holders(HK)

    assert holders.top10_date == "2025-12-31"
    assert holders.holder_count is None
    assert [item.name for item in holders.top10] == [
        "MIH Internet Holdings B.V.",
        "马化腾",
    ]
    assert holders.top10[0].ratio_pct == 22.8011
    assert holders.top10[0].holder_type == "股东"
    assert holders.top10[1].rank == 2


@pytest.mark.asyncio
async def test_hk_datacenter_empty_result_raises_market_closed():
    provider = _em_provider(
        lambda request: httpx.Response(200, json={"result": {"data": []}})
    )

    with pytest.raises(ProviderError) as raised:
        await provider.get_hk_share_structure(HK)
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY

    with pytest.raises(ProviderError) as raised:
        await provider.get_hk_major_holders(HK)
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_hk_datacenter_filter_uses_hk_secucode():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _hk_route(request)

    await _em_provider(handler).get_hk_major_holders(HK)

    assert any("00700.HK" in str(request.url) for request in captured)
