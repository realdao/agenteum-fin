"""stock_fundamental_snapshot 的服务端计算层。

移植自 workspace 技能 company-fundamental-analysis 的
`scripts/company_fundamental_data.py`，保持口径一致以便对拍：

- 盈利/成长：营收、归母、扣非、OCF、毛利率、净利率、ROE、ROA、DuPont（周转×权益乘数）、YoY
- 运营/债务：货币资金、应收、存货、应收天数（简化口径）、资产负债率、流动比率、有息负债
- 估值：TTM（最新报告期+上年年报-上年同期）与 PE/扣非PE/PS 自算
- 清洁度：投资收益、公允价值变动及其占净利比、商誉、长期股权投资

输入为 provider 层归一化后的纯 Python 结构：
`abstract` 为 {指标名: {期间: 原始值}}，报表为含 "报告日" 的记录列表。
所有函数为纯函数，不做 I/O。
"""

from __future__ import annotations

import math
import re
from typing import Any

AbstractData = dict[str, dict[str, Any]]
StatementRows = list[dict[str, Any]]


def num(value: Any) -> float | None:
    if value is None or value == "" or str(value).lower() in {"nan", "none", "--", "false"}:
        return None
    try:
        value = str(value).replace(",", "")
        if value.endswith("%"):
            return float(value[:-1]) / 100
        if value.endswith("亿"):
            return float(value[:-1]) * 1e8
        if value.endswith("万"):
            return float(value[:-1]) * 1e4
        return float(value)
    except (TypeError, ValueError):
        return None


def div(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def pct(x: float | None) -> float | None:
    return None if x is None else x * 100


def yi(x: float | None) -> float | None:
    return None if x is None else x / 1e8


def round_or_none(x: float | None, ndigits: int = 4) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), ndigits)


def metric(abstract: AbstractData, name: str, period: str) -> float | None:
    row = abstract.get(name)
    if row is None:
        return None
    return num(row.get(period))


def row_by_period(rows: StatementRows, period: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("报告日")) == period:
            return row
    return None


def annual_periods(abstract: AbstractData) -> list[str]:
    periods = {period for row in abstract.values() for period in row}
    return sorted(
        (p for p in periods if re.fullmatch(r"\d{4}1231", p)),
        reverse=True,
    )


def all_periods(abstract: AbstractData) -> list[str]:
    periods = {period for row in abstract.values() for period in row}
    return sorted(
        (p for p in periods if re.fullmatch(r"\d{8}", p)),
        reverse=True,
    )


def build_profitability_periods(
    abstract: AbstractData,
    bs_rows: StatementRows,
    inc_rows: StatementRows,
    periods: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for period in periods:
        revenue = metric(abstract, "营业总收入", period)
        net = metric(abstract, "归母净利润", period)
        deducted = metric(abstract, "扣非净利润", period)
        equity = metric(abstract, "股东权益合计(净资产)", period)
        ocf = metric(abstract, "经营现金流量净额", period)
        goodwill = metric(abstract, "商誉", period)
        bs_row = row_by_period(bs_rows, period)
        inc_row = row_by_period(inc_rows, period)
        assets = num(bs_row.get("资产总计")) if bs_row is not None else None
        gross_margin = None
        if inc_row is not None:
            income = num(inc_row.get("营业收入"))
            cost = num(inc_row.get("营业成本"))
            gross_margin = div((income or 0) - (cost or 0), income)
        output.append(
            {
                "period": period,
                "revenue_yi": round_or_none(yi(revenue), 4),
                "net_profit_yi": round_or_none(yi(net), 4),
                "deducted_net_profit_yi": round_or_none(yi(deducted), 4),
                "operating_cash_flow_yi": round_or_none(yi(ocf), 4),
                "gross_margin_pct": round_or_none(pct(gross_margin), 2),
                "net_margin_pct": round_or_none(pct(div(net, revenue)), 2),
                "roe_pct": round_or_none(pct(div(net, equity)), 2),
                "roa_pct": round_or_none(pct(div(net, assets)), 2),
                "asset_turnover": round_or_none(div(revenue, assets), 4),
                "equity_multiplier": round_or_none(div(assets, equity), 4),
                "goodwill_yi": round_or_none(yi(goodwill), 4),
            }
        )
    return output


def build_growth(annual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_period = {row["period"]: row for row in annual}
    growth: list[dict[str, Any]] = []
    for period in sorted(by_period.keys(), reverse=True):
        prev = f"{int(period[:4]) - 1}1231"
        if prev not in by_period:
            continue
        cur = by_period[period]
        old = by_period[prev]
        growth.append(
            {
                "period": period,
                "revenue_yoy_pct": round_or_none(
                    pct(
                        div(
                            (cur["revenue_yi"] or 0) - (old["revenue_yi"] or 0),
                            old["revenue_yi"],
                        )
                    ),
                    2,
                ),
                "net_profit_yoy_pct": round_or_none(
                    pct(
                        div(
                            (cur["net_profit_yi"] or 0) - (old["net_profit_yi"] or 0),
                            old["net_profit_yi"],
                        )
                    ),
                    2,
                ),
                "deducted_net_profit_yoy_pct": round_or_none(
                    pct(
                        div(
                            (cur["deducted_net_profit_yi"] or 0)
                            - (old["deducted_net_profit_yi"] or 0),
                            old["deducted_net_profit_yi"],
                        )
                    ),
                    2,
                ),
            }
        )
    return growth


def build_operations_solvency(
    bs_rows: StatementRows,
    abstract: AbstractData,
    periods: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        row = row_by_period(bs_rows, period)
        if row is None:
            continue
        revenue = metric(abstract, "营业总收入", period)
        ar = num(row.get("应收账款"))
        assets = num(row.get("资产总计"))
        liabilities = num(row.get("负债合计"))
        current_assets = num(row.get("流动资产合计"))
        current_liabilities = num(row.get("流动负债合计"))
        short_debt = num(row.get("短期借款")) or 0
        long_debt = num(row.get("长期借款")) or 0
        bond = num(row.get("应付债券")) or 0
        due_1y = num(row.get("一年内到期的非流动负债")) or 0
        rows.append(
            {
                "period": period,
                "cash_yi": round_or_none(yi(num(row.get("货币资金"))), 4),
                "trading_financial_assets_yi": round_or_none(yi(num(row.get("交易性金融资产"))), 4),
                "accounts_receivable_yi": round_or_none(yi(ar), 4),
                "inventory_yi": round_or_none(yi(num(row.get("存货"))), 4),
                "receivable_days_simple": round_or_none(
                    div(ar, revenue) * 365 if revenue and period.endswith("1231") else None,
                    2,
                ),
                "liability_ratio_pct": round_or_none(pct(div(liabilities, assets)), 2),
                "current_ratio": round_or_none(div(current_assets, current_liabilities), 4),
                "interest_bearing_debt_yi": round_or_none(
                    yi(short_debt + long_debt + bond + due_1y), 4
                ),
                "goodwill_yi": round_or_none(yi(num(row.get("商誉"))), 4),
                "long_term_equity_investment_yi": round_or_none(
                    yi(num(row.get("长期股权投资"))), 4
                ),
            }
        )
    return rows


def build_ttm_valuation(
    abstract: AbstractData,
    periods: list[str],
    market_cap: float | None,
) -> dict[str, Any]:
    """market_cap 单位为元；periods 为全部报告期（降序）。

    TTM = 最新报告期 + 上年年报 - 上年同期。最新报告期即年报、缺上年年报或
    缺上年同期时无法构成 TTM 窗口，返回空 dict（字段整体缺省为 null）。
    """
    if not periods or market_cap in (None, 0):
        return {}
    latest_q = periods[0]
    latest_annual = next((p for p in periods if p.endswith("1231")), None)
    prev_q_same = f"{int(latest_q[:4]) - 1}{latest_q[4:]}"
    if not (latest_annual and latest_q != latest_annual and prev_q_same in periods):
        return {}

    def ttm(name: str) -> float:
        return (
            (metric(abstract, name, latest_q) or 0)
            + (metric(abstract, name, latest_annual) or 0)
            - (metric(abstract, name, prev_q_same) or 0)
        )

    revenue = ttm("营业总收入")
    net = ttm("归母净利润")
    # 指标整体缺失（如港股无扣非口径）时扣非字段保持 None，而非显示 0。
    deducted = ttm("扣非净利润") if "扣非净利润" in abstract else None
    return {
        "ttm_revenue_yi": round_or_none(yi(revenue), 4),
        "ttm_net_profit_yi": round_or_none(yi(net), 4),
        "ttm_deducted_net_profit_yi": round_or_none(yi(deducted), 4),
        "pe_ttm_calculated": round_or_none(div(market_cap, net), 2),
        "pe_ttm_deducted": round_or_none(div(market_cap, deducted), 2),
        "ps_ttm": round_or_none(div(market_cap, revenue), 2),
    }


def build_balance_sheet_flags(
    annual: list[dict[str, Any]],
    operations: list[dict[str, Any]],
    inc_rows: StatementRows,
    latest_period: str,
) -> dict[str, Any]:
    latest_ops = next(
        (row for row in operations if row["period"] == latest_period),
        operations[0] if operations else {},
    )
    inc_row = row_by_period(inc_rows, latest_period)
    invest_income = num(inc_row.get("投资收益")) if inc_row is not None else None
    fair_value = num(inc_row.get("公允价值变动收益")) if inc_row is not None else None
    net = next(
        (row["net_profit_yi"] for row in annual if row["period"] == latest_period),
        None,
    )
    return {
        "interest_bearing_debt_yi": latest_ops.get("interest_bearing_debt_yi"),
        "trading_financial_assets_yi": latest_ops.get("trading_financial_assets_yi"),
        "goodwill_yi": latest_ops.get("goodwill_yi"),
        "long_term_equity_investment_yi": latest_ops.get("long_term_equity_investment_yi"),
        "investment_income_yi": round_or_none(yi(invest_income), 4),
        "fair_value_gain_yi": round_or_none(yi(fair_value), 4),
        "fair_value_gain_to_net_profit": round_or_none(div(yi(fair_value), net), 4),
    }
