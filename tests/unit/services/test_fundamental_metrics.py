"""fundamental_metrics 的口径测试，fixture 与参考实现对拍：

数据形态仿 company_fundamental_data.py 的 akshare 输入（abstract 为
{指标: {期间: 原始值}}，报表为含 "报告日" 的记录），期望值手工核算。
"""

import pytest

from src.services import fundamental_metrics as fm

ABSTRACT = {
    "营业总收入": {"20260331": 500e8, "20251231": 1700e8, "20250331": 480e8, "20241231": 1600e8},
    "归母净利润": {"20260331": 260e8, "20251231": 800e8, "20250331": 250e8, "20241231": 750e8},
    "扣非净利润": {"20260331": 259e8, "20251231": 790e8, "20250331": 248e8, "20241231": 740e8},
    "股东权益合计(净资产)": {"20251231": 2500e8, "20241231": 2200e8},
    "经营现金流量净额": {"20251231": 600e8, "20241231": 550e8},
    "商誉": {"20251231": None, "20241231": None},
}

BS_ROWS = [
    {
        "报告日": "20260331",
        "资产总计": 3100e8,
        "负债合计": 520e8,
        "流动资产合计": 2050e8,
        "流动负债合计": 410e8,
        "货币资金": 520e8,
        "交易性金融资产": None,
        "应收账款": 1.2e8,
        "存货": 610e8,
        "短期借款": 10e8,
        "长期借款": 20e8,
        "应付债券": None,
        "一年内到期的非流动负债": 5e8,
        "商誉": None,
        "长期股权投资": 2e8,
    },
    {
        "报告日": "20251231",
        "资产总计": 3000e8,
        "负债合计": 500e8,
        "流动资产合计": 2000e8,
        "流动负债合计": 400e8,
        "货币资金": 500e8,
        "交易性金融资产": None,
        "应收账款": 1e8,
        "存货": 600e8,
        "短期借款": 10e8,
        "长期借款": 20e8,
        "应付债券": None,
        "一年内到期的非流动负债": 5e8,
        "商誉": None,
        "长期股权投资": 2e8,
    },
    {
        "报告日": "20241231",
        "资产总计": 2800e8,
        "负债合计": 480e8,
        "流动资产合计": 1800e8,
        "流动负债合计": 380e8,
        "货币资金": 450e8,
        "交易性金融资产": None,
        "应收账款": 0.9e8,
        "存货": 550e8,
        "短期借款": 8e8,
        "长期借款": 18e8,
        "应付债券": None,
        "一年内到期的非流动负债": 4e8,
        "商誉": None,
        "长期股权投资": 1.8e8,
    },
]

INC_ROWS = [
    {
        "报告日": "20251231",
        "营业收入": 1690e8,
        "营业成本": 150e8,
        "投资收益": 0.5e8,
        "公允价值变动收益": 0.8e8,
    },
    {
        "报告日": "20241231",
        "营业收入": 1590e8,
        "营业成本": 160e8,
        "投资收益": 0.3e8,
        "公允价值变动收益": 0.2e8,
    },
]


def test_num_parses_chinese_magnitude_and_percent_strings():
    assert fm.num("1,234.5") == 1234.5
    assert fm.num("12%") == 0.12
    assert fm.num("3亿") == 3e8
    assert fm.num("5万") == 5e4
    assert fm.num(1234.0) == 1234.0
    for bad in (None, "", "nan", "None", "--", "false", "abc"):
        assert fm.num(bad) is None


def test_div_pct_yi_round_helpers():
    assert fm.div(1, 0) is None
    assert fm.div(None, 2) is None
    assert fm.div(1, 4) == 0.25
    assert fm.pct(0.5) == 50
    assert fm.yi(2e8) == 2
    assert fm.round_or_none(float("nan")) is None
    assert fm.round_or_none(1.005, 2) == 1.0


def test_period_discovery_from_abstract():
    assert fm.annual_periods(ABSTRACT) == ["20251231", "20241231"]
    assert fm.all_periods(ABSTRACT) == ["20260331", "20251231", "20250331", "20241231"]


def test_build_profitability_periods_computes_margins_and_dupont():
    rows = fm.build_profitability_periods(ABSTRACT, BS_ROWS, INC_ROWS, ["20251231"])
    row = rows[0]

    assert row["revenue_yi"] == 1700
    assert row["net_profit_yi"] == 800
    assert row["deducted_net_profit_yi"] == 790
    assert row["operating_cash_flow_yi"] == 600
    assert row["gross_margin_pct"] == pytest.approx(91.12, abs=0.01)
    assert row["net_margin_pct"] == pytest.approx(47.06, abs=0.01)
    assert row["roe_pct"] == pytest.approx(32.0, abs=0.01)
    assert row["roa_pct"] == pytest.approx(26.67, abs=0.01)
    assert row["asset_turnover"] == pytest.approx(0.5667, abs=0.001)
    assert row["equity_multiplier"] == pytest.approx(1.2, abs=0.001)
    assert row["goodwill_yi"] is None


def test_build_profitability_periods_degrades_without_statements():
    rows = fm.build_profitability_periods(ABSTRACT, [], [], ["20251231"])
    row = rows[0]

    assert row["revenue_yi"] == 1700
    assert row["gross_margin_pct"] is None
    assert row["roa_pct"] is None
    assert row["asset_turnover"] is None
    assert row["equity_multiplier"] is None


def test_build_growth_uses_deducted_preferred_series():
    annual = fm.build_profitability_periods(ABSTRACT, BS_ROWS, INC_ROWS, ["20251231", "20241231"])
    growth = fm.build_growth(annual)

    assert len(growth) == 1
    row = growth[0]
    assert row["period"] == "20251231"
    assert row["revenue_yoy_pct"] == pytest.approx(6.25, abs=0.01)
    assert row["net_profit_yoy_pct"] == pytest.approx(6.67, abs=0.01)
    assert row["deducted_net_profit_yoy_pct"] == pytest.approx(6.76, abs=0.01)


def test_build_operations_solvency_computes_debt_and_liquidity():
    rows = fm.build_operations_solvency(BS_ROWS, ABSTRACT, ["20251231", "20260331"])
    annual, quarter = rows[0], rows[1]

    assert annual["period"] == "20251231"
    assert annual["cash_yi"] == 500
    assert annual["accounts_receivable_yi"] == 1
    assert annual["inventory_yi"] == 600
    assert annual["receivable_days_simple"] == pytest.approx(0.21, abs=0.01)
    assert annual["liability_ratio_pct"] == pytest.approx(16.67, abs=0.01)
    assert annual["current_ratio"] == pytest.approx(5.0, abs=0.01)
    assert annual["interest_bearing_debt_yi"] == 35
    assert annual["long_term_equity_investment_yi"] == 2

    # 应收天数仅年报期计算
    assert quarter["period"] == "20260331"
    assert quarter["receivable_days_simple"] is None


def test_build_ttm_valuation_uses_latest_quarter_plus_annual_minus_prior_quarter():
    ttm = fm.build_ttm_valuation(ABSTRACT, fm.all_periods(ABSTRACT), 16151.2e8)

    assert ttm["ttm_revenue_yi"] == 1720
    assert ttm["ttm_net_profit_yi"] == 810
    assert ttm["ttm_deducted_net_profit_yi"] == 801
    assert ttm["pe_ttm_calculated"] == pytest.approx(19.94, abs=0.01)
    assert ttm["pe_ttm_deducted"] == pytest.approx(20.16, abs=0.01)
    assert ttm["ps_ttm"] == pytest.approx(9.39, abs=0.01)


def test_build_ttm_valuation_returns_empty_when_window_incomplete():
    # 最新期即年报：无法构成 TTM 窗口
    annual_only = {
        name: {p: v for p, v in row.items() if p.endswith("1231")}
        for name, row in ABSTRACT.items()
    }
    assert fm.build_ttm_valuation(annual_only, fm.all_periods(annual_only), 1e10) == {}
    # 缺市值
    assert fm.build_ttm_valuation(ABSTRACT, fm.all_periods(ABSTRACT), None) == {}
    assert fm.build_ttm_valuation(ABSTRACT, fm.all_periods(ABSTRACT), 0) == {}


def test_build_balance_sheet_flags_reads_latest_annual_signals():
    annual = fm.build_profitability_periods(ABSTRACT, BS_ROWS, INC_ROWS, ["20251231", "20241231"])
    ops = fm.build_operations_solvency(BS_ROWS, ABSTRACT, ["20251231"])
    flags = fm.build_balance_sheet_flags(annual, ops, INC_ROWS, "20251231")

    assert flags["interest_bearing_debt_yi"] == 35
    assert flags["trading_financial_assets_yi"] is None
    assert flags["long_term_equity_investment_yi"] == 2
    assert flags["investment_income_yi"] == 0.5
    assert flags["fair_value_gain_yi"] == 0.8
    assert flags["fair_value_gain_to_net_profit"] == pytest.approx(0.001, abs=0.0001)
