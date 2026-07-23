"""fundamental_metrics_hk 的港股口径测试（IFRS 科目映射、TTM 复用、比率直读）。"""

import pytest

from src.services import fundamental_metrics as fm
from src.services import fundamental_metrics_hk as hkm

INDICATORS_ANNUAL = [
    {
        "REPORT_DATE": "2025-12-31 00:00:00",
        "OPERATE_INCOME": 7500e8,
        "OPERATE_INCOME_YOY": 13.86,
        "HOLDER_PROFIT": 2250e8,
        "HOLDER_PROFIT_YOY": 15.85,
        "GROSS_PROFIT_RATIO": 56.21,
        "NET_PROFIT_RATIO": 30.57,
        "ROE_AVG": 21.13,
        "ROA": 11.77,
    },
    {
        "REPORT_DATE": "2024-12-31 00:00:00",
        "OPERATE_INCOME": 6600e8,
        "OPERATE_INCOME_YOY": 8.41,
        "HOLDER_PROFIT": 1940e8,
        "HOLDER_PROFIT_YOY": 68.44,
        "GROSS_PROFIT_RATIO": 52.9,
        "NET_PROFIT_RATIO": 29.76,
        "ROE_AVG": 21.78,
        "ROA": 11.56,
    },
]

INDICATORS_REPORT = [
    {
        "REPORT_DATE": "2026-03-31 00:00:00",
        "OPERATE_INCOME": 1960e8,
        "HOLDER_PROFIT": 581e8,
        "GROSS_PROFIT_RATIO": 56.64,
        "ROE_AVG": 5.09,
    },
    INDICATORS_ANNUAL[0],
    {"REPORT_DATE": "2025-03-31 00:00:00", "OPERATE_INCOME": 1800e8, "HOLDER_PROFIT": 478e8},
]


def _bs_rows(period: str) -> list[dict]:
    items = {
        "总资产": 19000e8,
        "总负债": 7400e8,
        "股东权益": 10800e8,
        "流动资产合计": 6000e8,
        "流动负债合计": 4000e8,
        "现金及等价物": 2500e8,
        "应收帐款": 500e8,
        "存货": 30e8,
        "短期贷款": 400e8,
        "长期贷款": 1500e8,
        "融资租赁负债(流动)": 30e8,
        "融资租赁负债(非流动)": 120e8,
        "联营公司权益": 2600e8,
        "合营公司权益": 100e8,
    }
    return [
        {"REPORT_DATE": period, "STD_ITEM_NAME": name, "AMOUNT": value}
        for name, value in items.items()
    ]


BS_PIVOT = hkm.pivot_statement(_bs_rows("2025-12-31 00:00:00"))
CF_PIVOT = hkm.pivot_statement(
    [
        {
            "REPORT_DATE": "2025-12-31 00:00:00",
            "STD_ITEM_NAME": "经营业务现金净额",
            "AMOUNT": 3030e8,
        }
    ]
)


def test_hk_period_normalizes_date_strings():
    assert hkm.hk_period("2025-12-31 00:00:00") == "20251231"
    assert hkm.hk_period("2025-12-31") == "20251231"
    assert hkm.hk_period("20251231") == "20251231"
    assert hkm.hk_period(None) == ""


def test_pivot_statement_groups_amounts_by_period():
    pivot = hkm.pivot_statement(
        [
            {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "总资产", "AMOUNT": 100},
            {"REPORT_DATE": "2025-12-31", "STD_ITEM_NAME": "总负债", "AMOUNT": "40"},
            {"REPORT_DATE": "2024-12-31", "STD_ITEM_NAME": "总资产", "AMOUNT": 90},
        ]
    )

    assert pivot == {
        "20251231": {"总资产": 100, "总负债": 40},
        "20241231": {"总资产": 90},
    }
    assert hkm.item_amount(pivot, "20251231", "总资产") == 100
    assert hkm.item_amount(pivot, "20251231", "不存在", "总负债") == 40
    assert hkm.item_amount(pivot, "20231231", "总资产") is None


def test_hk_pseudo_abstract_feeds_a_share_ttm_calculation():
    pseudo = hkm.build_hk_pseudo_abstract(INDICATORS_REPORT)
    ttm = fm.build_ttm_valuation(pseudo, fm.all_periods(pseudo), 40500e8)

    assert ttm["ttm_revenue_yi"] == 7660  # 1960 + 7500 - 1800
    assert ttm["ttm_net_profit_yi"] == 2353  # 581 + 2250 - 478
    assert ttm["pe_ttm_calculated"] == pytest.approx(17.21, abs=0.01)
    # 伪 abstract 无扣非指标：扣非字段为 None 而非 0
    assert ttm["ttm_deducted_net_profit_yi"] is None
    assert ttm["pe_ttm_deducted"] is None


def test_build_hk_profitability_annual_reads_ratios_directly():
    rows = hkm.build_hk_profitability_annual(INDICATORS_ANNUAL, BS_PIVOT, CF_PIVOT, 5)
    row = rows[0]

    assert row["period"] == "20251231"
    assert row["revenue_yi"] == 7500
    assert row["net_profit_yi"] == 2250
    assert row["deducted_net_profit_yi"] is None
    assert row["operating_cash_flow_yi"] == 3030
    assert row["gross_margin_pct"] == 56.21
    assert row["net_margin_pct"] == 30.57
    assert row["roe_pct"] == 21.13
    assert row["roa_pct"] == 11.77
    assert row["asset_turnover"] == pytest.approx(0.3947, abs=0.001)
    assert row["equity_multiplier"] == pytest.approx(1.7593, abs=0.001)
    assert row["goodwill_yi"] is None


def test_build_hk_profitability_annual_degrades_without_statements():
    rows = hkm.build_hk_profitability_annual(INDICATORS_ANNUAL, {}, {}, 5)
    row = rows[0]

    assert row["revenue_yi"] == 7500
    assert row["operating_cash_flow_yi"] is None
    assert row["asset_turnover"] is None
    assert row["equity_multiplier"] is None


def test_build_hk_latest_quarter_picks_latest_report_period():
    row = hkm.build_hk_latest_quarter(INDICATORS_REPORT, BS_PIVOT)

    assert row["period"] == "20260331"
    assert row["revenue_yi"] == 1960
    assert hkm.build_hk_latest_quarter([], BS_PIVOT) is None


def test_build_hk_growth_uses_source_yoy_fields():
    growth = hkm.build_hk_growth(INDICATORS_ANNUAL)

    assert growth[0] == {
        "period": "20251231",
        "revenue_yoy_pct": 13.86,
        "net_profit_yoy_pct": 15.85,
        "deducted_net_profit_yoy_pct": None,
    }


def test_build_hk_operations_maps_ifrs_items():
    revenue_map = hkm.revenue_by_period(INDICATORS_ANNUAL)
    rows = hkm.build_hk_operations(BS_PIVOT, revenue_map, ["20251231"])
    row = rows[0]

    assert row["cash_yi"] == 2500
    assert row["accounts_receivable_yi"] == 500
    assert row["inventory_yi"] == 30
    assert row["receivable_days_simple"] == pytest.approx(24.33, abs=0.01)
    assert row["liability_ratio_pct"] == pytest.approx(38.95, abs=0.01)
    assert row["current_ratio"] == 1.5
    assert row["interest_bearing_debt_yi"] == 2050
    assert row["long_term_equity_investment_yi"] == 2700
    assert row["goodwill_yi"] is None
    # 期间不在资产负债表中时跳过该行
    assert hkm.build_hk_operations(BS_PIVOT, revenue_map, ["20231231"]) == []


def test_build_hk_flags_uses_associates_income_as_investment_income():
    inc_pivot = hkm.pivot_statement(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "STD_ITEM_NAME": "应占联营公司溢利",
                "AMOUNT": 250e8,
            },
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "STD_ITEM_NAME": "应占合营公司溢利",
                "AMOUNT": 5e8,
            },
        ]
    )
    flags = hkm.build_hk_flags(BS_PIVOT, inc_pivot, "20251231")

    assert flags["investment_income_yi"] == 255
    assert flags["interest_bearing_debt_yi"] == 2050
    assert flags["fair_value_gain_yi"] is None
    assert flags["fair_value_gain_to_net_profit"] is None
    # 利润表缺失时投资收益为 None 而非 0
    flags_no_inc = hkm.build_hk_flags(BS_PIVOT, {}, "20251231")
    assert flags_no_inc["investment_income_yi"] is None
