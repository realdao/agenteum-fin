"""stock_fundamental_snapshot 港股（HK）计算层：东财港股接口 → 统一快照字段的映射。

数据源为 akshare 东财港股接口族（字段与口径经 playground/hk_fundamental_probe.py
实测，标的腾讯 00700.HK）：

- 主要指标（`stock_financial_hk_analysis_indicator_em`）：比率字段已是百分数
  （如 GROSS_PROFIT_RATIO=56.21），ROE 为加权平均口径（ROE_AVG）。
- 三大报表（`stock_financial_hk_report_em`）：长表（REPORT_DATE + STD_ITEM_NAME
  + AMOUNT），IFRS 科目口径，与 A 股快照的映射关系：
  现金及等价物→cash、应收帐款→AR、短期贷款+长期贷款+融资租赁负债→有息负债、
  联营公司权益+合营公司权益→长期股权投资、经营业务现金净额→OCF。

所有函数为纯函数，不做 I/O；金额单位统一换算为亿（港元）。
"""

from __future__ import annotations

from typing import Any

from src.services.fundamental_metrics import div, num, pct, round_or_none, yi

IndicatorRows = list[dict[str, Any]]
StatementPivot = dict[str, dict[str, float | None]]


def hk_period(value: Any) -> str:
    """'2025-12-31 00:00:00' / '2025-12-31' / '20251231' -> '20251231'。"""
    return str(value or "")[:10].replace("-", "")


def pivot_statement(rows: list[dict[str, Any]]) -> StatementPivot:
    """长表记录透视为 {期间(YYYYMMDD): {科目名: 金额}}。"""
    pivot: StatementPivot = {}
    for row in rows:
        period = hk_period(row.get("REPORT_DATE"))
        item = row.get("STD_ITEM_NAME")
        if not period or item is None:
            continue
        pivot.setdefault(period, {})[str(item)] = num(row.get("AMOUNT"))
    return pivot


def item_amount(
    pivot: StatementPivot,
    period: str,
    *items: str,
) -> float | None:
    """按别名顺序取第一个非 None 的科目金额；期间不存在返回 None。"""
    row = pivot.get(period)
    if row is None:
        return None
    for item in items:
        if row.get(item) is not None:
            return row[item]
    return None


def sorted_periods(pivot: StatementPivot) -> list[str]:
    return sorted(pivot.keys(), reverse=True)


def build_hk_pseudo_abstract(indicator_rows: IndicatorRows) -> dict[str, dict[str, Any]]:
    """把报告期主要指标包装成 A 股 abstract 形态，复用 TTM 窗口计算。"""
    revenue: dict[str, Any] = {}
    net: dict[str, Any] = {}
    for row in indicator_rows:
        period = hk_period(row.get("REPORT_DATE"))
        if not period:
            continue
        revenue[period] = row.get("OPERATE_INCOME")
        net[period] = row.get("HOLDER_PROFIT")
    return {"营业总收入": revenue, "归母净利润": net}


def revenue_by_period(indicator_rows: IndicatorRows) -> dict[str, float | None]:
    return {
        period: num(row.get("OPERATE_INCOME"))
        for row in indicator_rows
        if (period := hk_period(row.get("REPORT_DATE")))
    }


def _profitability_row(
    row: dict[str, Any],
    bs_pivot: StatementPivot,
    ocf_by_period: dict[str, float | None],
) -> dict[str, Any]:
    period = hk_period(row.get("REPORT_DATE"))
    revenue = num(row.get("OPERATE_INCOME"))
    assets = item_amount(bs_pivot, period, "总资产")
    equity = item_amount(bs_pivot, period, "股东权益")
    return {
        "period": period,
        "revenue_yi": round_or_none(yi(revenue), 4),
        "net_profit_yi": round_or_none(yi(num(row.get("HOLDER_PROFIT"))), 4),
        "deducted_net_profit_yi": None,  # 港股无扣非披露口径
        "operating_cash_flow_yi": round_or_none(yi(ocf_by_period.get(period)), 4),
        "gross_margin_pct": round_or_none(num(row.get("GROSS_PROFIT_RATIO")), 2),
        "net_margin_pct": round_or_none(num(row.get("NET_PROFIT_RATIO")), 2),
        "roe_pct": round_or_none(num(row.get("ROE_AVG")), 2),
        "roa_pct": round_or_none(num(row.get("ROA")), 2),
        "asset_turnover": round_or_none(div(revenue, assets), 4),
        "equity_multiplier": round_or_none(div(assets, equity), 4),
        "goodwill_yi": None,  # 港股商誉不单列（并入无形资产等科目）
    }


def build_hk_profitability_annual(
    annual_rows: IndicatorRows,
    bs_pivot: StatementPivot,
    cf_pivot: StatementPivot,
    years: int,
) -> list[dict[str, Any]]:
    ocf_by_period = {
        period: items.get("经营业务现金净额") for period, items in cf_pivot.items()
    }
    rows = sorted(annual_rows, key=lambda row: hk_period(row.get("REPORT_DATE")), reverse=True)
    return [_profitability_row(row, bs_pivot, ocf_by_period) for row in rows[:years]]


def build_hk_latest_quarter(
    report_rows: IndicatorRows,
    bs_pivot: StatementPivot,
) -> dict[str, Any] | None:
    if not report_rows:
        return None
    latest = max(report_rows, key=lambda row: hk_period(row.get("REPORT_DATE")))
    return _profitability_row(latest, bs_pivot, {})


def build_hk_growth(annual_rows: IndicatorRows) -> list[dict[str, Any]]:
    rows = sorted(annual_rows, key=lambda row: hk_period(row.get("REPORT_DATE")), reverse=True)
    return [
        {
            "period": hk_period(row.get("REPORT_DATE")),
            "revenue_yoy_pct": round_or_none(num(row.get("OPERATE_INCOME_YOY")), 2),
            "net_profit_yoy_pct": round_or_none(num(row.get("HOLDER_PROFIT_YOY")), 2),
            "deducted_net_profit_yoy_pct": None,  # 港股无扣非披露口径
        }
        for row in rows
    ]


def build_hk_operations(
    bs_pivot: StatementPivot,
    revenue_by_period_map: dict[str, float | None],
    periods: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        if period not in bs_pivot:
            continue
        assets = item_amount(bs_pivot, period, "总资产")
        liabilities = item_amount(bs_pivot, period, "总负债")
        current_assets = item_amount(bs_pivot, period, "流动资产合计")
        current_liabilities = item_amount(bs_pivot, period, "流动负债合计")
        ar = item_amount(bs_pivot, period, "应收帐款", "应收账款")
        revenue = revenue_by_period_map.get(period)
        interest_bearing = sum(
            item_amount(bs_pivot, period, item) or 0
            for item in ("短期贷款", "长期贷款", "融资租赁负债(流动)", "融资租赁负债(非流动)")
        )
        lt_equity = sum(
            item_amount(bs_pivot, period, item) or 0
            for item in ("联营公司权益", "合营公司权益")
        )
        rows.append(
            {
                "period": period,
                "cash_yi": round_or_none(yi(item_amount(bs_pivot, period, "现金及等价物")), 4),
                "trading_financial_assets_yi": round_or_none(
                    yi(item_amount(bs_pivot, period, "交易性金融资产(流动)")), 4
                ),
                "accounts_receivable_yi": round_or_none(yi(ar), 4),
                "inventory_yi": round_or_none(yi(item_amount(bs_pivot, period, "存货")), 4),
                "receivable_days_simple": round_or_none(
                    div(ar, revenue) * 365 if revenue and period.endswith("1231") else None,
                    2,
                ),
                "liability_ratio_pct": round_or_none(pct(div(liabilities, assets)), 2),
                "current_ratio": round_or_none(div(current_assets, current_liabilities), 4),
                "interest_bearing_debt_yi": round_or_none(yi(interest_bearing), 4),
                "goodwill_yi": None,  # 港股商誉不单列
                "long_term_equity_investment_yi": round_or_none(yi(lt_equity), 4),
            }
        )
    return rows


def build_hk_flags(
    bs_pivot: StatementPivot,
    inc_pivot: StatementPivot,
    latest_period: str,
) -> dict[str, Any]:
    operations = build_hk_operations(bs_pivot, {}, [latest_period])
    latest_ops = operations[0] if operations else {}
    investment_income: float | None = None
    if latest_period in inc_pivot:
        investment_income = sum(
            item_amount(inc_pivot, latest_period, item) or 0
            for item in ("应占联营公司溢利", "应占合营公司溢利")
        )
    return {
        "interest_bearing_debt_yi": latest_ops.get("interest_bearing_debt_yi"),
        "trading_financial_assets_yi": latest_ops.get("trading_financial_assets_yi"),
        "goodwill_yi": None,
        "long_term_equity_investment_yi": latest_ops.get("long_term_equity_investment_yi"),
        # 港股口径：应占联营/合营公司溢利（权益法投资收益）
        "investment_income_yi": round_or_none(yi(investment_income), 4),
        "fair_value_gain_yi": None,  # 港股利润表不单列
        "fair_value_gain_to_net_profit": None,
    }
