from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from datetime import date, datetime
from typing import Any

import akshare as ak
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=FutureWarning)


def clean_code(code: str) -> str:
    digits = re.sub(r"\D", "", code)
    if len(digits) < 6:
        digits = digits.zfill(6)
    return digits[-6:]


def market_prefix(code: str) -> str:
    return "SH" if code.startswith(("6", "9")) else ("BJ" if code.startswith("8") else "SZ")


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


def scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        df = df.head(limit)
    return [{str(k): scalar(v) for k, v in row.items()} for row in df.to_dict("records")]


def session_no_proxy() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session


def tencent_quote(code: str) -> dict[str, Any]:
    prefix = "sh" if code.startswith(("6", "9")) else ("bj" if code.startswith("8") else "sz")
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    errors: list[str] = []
    text = ""
    for getter in (requests.get, session_no_proxy().get):
        try:
            r = getter(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            r.encoding = "gbk"
            text = r.text
            break
        except Exception as exc:
            errors.append(repr(exc))
    if '"' not in text:
        return {"error": text[:120] or "; ".join(errors)}
    vals = text.split('"')[1].split("~")
    return {
        "name": vals[1],
        "price": num(vals[3]),
        "change_pct": num(vals[32]),
        "pe_ttm_source": num(vals[39]),
        "market_cap_yi": num(vals[44]),
        "float_market_cap_yi": num(vals[45]),
        "pb_source": num(vals[46]),
        "pe_static_source": num(vals[52]) if len(vals) > 52 else None,
    }


def get_abstract(code: str) -> pd.DataFrame:
    return ak.stock_financial_abstract(code).set_index("指标")


def metric(abs_df: pd.DataFrame, name: str, period: str) -> float | None:
    if name not in abs_df.index or period not in abs_df.columns:
        return None
    row = abs_df.loc[name]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return num(row.get(period))


def row_by_period(df: pd.DataFrame, period: str) -> pd.Series | None:
    rows = df[df["报告日"].astype(str) == period]
    if rows.empty:
        return None
    return rows.iloc[0]


def annual_periods(abs_df: pd.DataFrame) -> list[str]:
    periods = [c for c in abs_df.columns if re.fullmatch(r"\d{4}1231", str(c))]
    return sorted(periods, reverse=True)


def latest_periods(abs_df: pd.DataFrame) -> list[str]:
    periods = [c for c in abs_df.columns if re.fullmatch(r"\d{8}", str(c))]
    return sorted(periods, reverse=True)


def build_annual_metrics(abs_df: pd.DataFrame, bs: pd.DataFrame, inc: pd.DataFrame, periods: list[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for period in periods:
        revenue = metric(abs_df, "营业总收入", period)
        net = metric(abs_df, "归母净利润", period)
        deducted = metric(abs_df, "扣非净利润", period)
        equity = metric(abs_df, "股东权益合计(净资产)", period)
        ocf = metric(abs_df, "经营现金流量净额", period)
        goodwill = metric(abs_df, "商誉", period)
        bs_row = row_by_period(bs, period)
        inc_row = row_by_period(inc, period)
        assets = num(bs_row.get("资产总计")) if bs_row is not None else None
        gross_margin = None
        if inc_row is not None:
            income = num(inc_row.get("营业收入"))
            cost = num(inc_row.get("营业成本"))
            gross_margin = div((income or 0) - (cost or 0), income)
        asset_turnover = div(revenue, assets)
        net_margin = div(net, revenue)
        roe = div(net, equity)
        roa = div(net, assets)
        output.append(
            {
                "period": period,
                "revenue_yi": round_or_none(yi(revenue), 4),
                "net_profit_yi": round_or_none(yi(net), 4),
                "deducted_net_profit_yi": round_or_none(yi(deducted), 4),
                "operating_cash_flow_yi": round_or_none(yi(ocf), 4),
                "gross_margin_pct": round_or_none(pct(gross_margin), 2),
                "net_margin_pct": round_or_none(pct(net_margin), 2),
                "roe_pct": round_or_none(pct(roe), 2),
                "roa_pct": round_or_none(pct(roa), 2),
                "asset_turnover": round_or_none(asset_turnover, 4),
                "equity_multiplier": round_or_none(div(assets, equity), 4),
                "goodwill_yi": round_or_none(yi(goodwill), 4),
            }
        )
    return output


def build_growth(annual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_period = {r["period"]: r for r in annual}
    growth = []
    periods = sorted(by_period.keys(), reverse=True)
    for period in periods:
        prev = f"{int(period[:4]) - 1}1231"
        if prev not in by_period:
            continue
        cur = by_period[period]
        old = by_period[prev]
        growth.append(
            {
                "period": period,
                "revenue_yoy_pct": round_or_none(pct(div((cur["revenue_yi"] or 0) - (old["revenue_yi"] or 0), old["revenue_yi"])), 2),
                "net_profit_yoy_pct": round_or_none(pct(div((cur["net_profit_yi"] or 0) - (old["net_profit_yi"] or 0), old["net_profit_yi"])), 2),
                "deducted_net_profit_yoy_pct": round_or_none(
                    pct(div((cur["deducted_net_profit_yi"] or 0) - (old["deducted_net_profit_yi"] or 0), old["deducted_net_profit_yi"])),
                    2,
                ),
            }
        )
    return growth


def build_operations_and_debt(bs: pd.DataFrame, abs_df: pd.DataFrame, periods: list[str]) -> list[dict[str, Any]]:
    rows = []
    for period in periods:
        row = row_by_period(bs, period)
        if row is None:
            continue
        revenue = metric(abs_df, "营业总收入", period)
        ar = num(row.get("应收账款"))
        inv = num(row.get("存货"))
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
                "inventory_yi": round_or_none(yi(inv), 4),
                "receivable_days_simple": round_or_none(div(ar, revenue) * 365 if revenue and period.endswith("1231") else None, 2),
                "liability_ratio_pct": round_or_none(pct(div(liabilities, assets)), 2),
                "current_ratio": round_or_none(div(current_assets, current_liabilities), 4),
                "interest_bearing_debt_yi": round_or_none(yi(short_debt + long_debt + bond + due_1y), 4),
                "goodwill_yi": round_or_none(yi(num(row.get("商誉"))), 4),
                "long_term_equity_investment_yi": round_or_none(yi(num(row.get("长期股权投资"))), 4),
            }
        )
    return rows


def build_valuation(quote: dict[str, Any], abs_df: pd.DataFrame, periods: list[str]) -> dict[str, Any]:
    latest_q = periods[0]
    latest_annual = next((p for p in periods if p.endswith("1231")), None)
    prev_q_same = f"{int(latest_q[:4]) - 1}{latest_q[4:]}"
    market_cap = (quote.get("market_cap_yi") or 0) * 1e8
    ttm = {}
    if latest_annual and latest_q != latest_annual and prev_q_same in periods:
        revenue = (metric(abs_df, "营业总收入", latest_q) or 0) + (metric(abs_df, "营业总收入", latest_annual) or 0) - (metric(abs_df, "营业总收入", prev_q_same) or 0)
        net = (metric(abs_df, "归母净利润", latest_q) or 0) + (metric(abs_df, "归母净利润", latest_annual) or 0) - (metric(abs_df, "归母净利润", prev_q_same) or 0)
        deducted = (metric(abs_df, "扣非净利润", latest_q) or 0) + (metric(abs_df, "扣非净利润", latest_annual) or 0) - (metric(abs_df, "扣非净利润", prev_q_same) or 0)
        ttm = {
            "ttm_revenue_yi": round_or_none(yi(revenue), 4),
            "ttm_net_profit_yi": round_or_none(yi(net), 4),
            "ttm_deducted_net_profit_yi": round_or_none(yi(deducted), 4),
            "pe_ttm_calculated": round_or_none(div(market_cap, net), 2),
            "pe_ttm_deducted": round_or_none(div(market_cap, deducted), 2),
            "ps_ttm": round_or_none(div(market_cap, revenue), 2),
        }
    return {
        "price": quote.get("price"),
        "market_cap_yi": quote.get("market_cap_yi"),
        "float_market_cap_yi": quote.get("float_market_cap_yi"),
        "pe_ttm_source": quote.get("pe_ttm_source"),
        "pb_source": quote.get("pb_source"),
        "pe_static_source": quote.get("pe_static_source"),
        **ttm,
    }


def business_data(code: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        intro = ak.stock_zyjs_ths(code)
        out["intro"] = records(intro)
    except Exception as exc:
        out["intro_error"] = repr(exc)
    try:
        comp = ak.stock_zygc_em(f"{market_prefix(code)}{code}")
        latest_date = str(comp["报告日期"].max())
        out["composition_latest_date"] = latest_date
        out["composition"] = records(comp[comp["报告日期"].astype(str) == latest_date])
    except Exception as exc:
        out["composition_error"] = repr(exc)
    return out


def clean_balance_sheet_checks(annual: list[dict[str, Any]], ops: list[dict[str, Any]], inc: pd.DataFrame, latest_period: str) -> dict[str, Any]:
    latest_ops = next((r for r in ops if r["period"] == latest_period), ops[0] if ops else {})
    inc_row = row_by_period(inc, latest_period)
    invest_income = num(inc_row.get("投资收益")) if inc_row is not None else None
    fair_value = num(inc_row.get("公允价值变动收益")) if inc_row is not None else None
    net = next((r["net_profit_yi"] for r in annual if r["period"] == latest_period), None)
    return {
        "business_focus": "check business.composition: main product/industry revenue concentration",
        "interest_bearing_debt_yi": latest_ops.get("interest_bearing_debt_yi"),
        "trading_financial_assets_yi": latest_ops.get("trading_financial_assets_yi"),
        "goodwill_yi": latest_ops.get("goodwill_yi"),
        "long_term_equity_investment_yi": latest_ops.get("long_term_equity_investment_yi"),
        "investment_income_yi": round_or_none(yi(invest_income), 4),
        "fair_value_gain_yi": round_or_none(yi(fair_value), 4),
        "fair_value_gain_to_net_profit": round_or_none(div(yi(fair_value), net), 4),
    }


def to_yaml(value: Any, indent: int = 0) -> str:
    space = "  " * indent
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{space}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{space}{k}: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{space}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{space}-")
                lines.append(to_yaml(item, indent + 1))
            else:
                lines.append(f"{space}- {json.dumps(item, ensure_ascii=False)}")
        return "\n".join(lines)
    return f"{space}{json.dumps(value, ensure_ascii=False)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--annual-years", type=int, default=5)
    args = parser.parse_args()

    code = clean_code(args.code)
    quote = tencent_quote(code)
    abs_df = get_abstract(code)
    all_periods = latest_periods(abs_df)
    annual = annual_periods(abs_df)[: args.annual_years]
    bs = ak.stock_financial_report_sina(stock=f"{market_prefix(code).lower()}{code}", symbol="资产负债表")
    inc = ak.stock_financial_report_sina(stock=f"{market_prefix(code).lower()}{code}", symbol="利润表")

    annual_metrics = build_annual_metrics(abs_df, bs, inc, annual)
    ops_periods = sorted(set(annual[:3] + all_periods[:1]), reverse=True)
    operations = build_operations_and_debt(bs, abs_df, ops_periods)
    holders = ak.stock_main_stock_holder(stock=code)
    latest_holder_date = holders["截至日期"].max() if not holders.empty else None
    latest_holder_date_value = scalar(latest_holder_date) if latest_holder_date is not None else None

    result = {
        "meta": {
            "code": code,
            "name": quote.get("name"),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": ["akshare", "tencent_quote"],
        },
        "framework_sections": [
            "company_positioning",
            "business_split",
            "revenue_drivers",
            "profit_drivers",
            "growth",
            "operations",
            "solvency",
            "business_model",
            "competition_and_moat",
            "investment_potential",
            "balance_sheet_cleanliness",
            "tracking_indicators",
            "missing_information",
        ],
        "quote_and_valuation": build_valuation(quote, abs_df, all_periods),
        "business": business_data(code),
        "shareholders": {
            "latest_date": latest_holder_date_value,
            "top10": records(holders[holders["截至日期"] == latest_holder_date].head(10)) if latest_holder_date else [],
        },
        "profitability_annual": annual_metrics,
        "growth_annual": build_growth(annual_metrics),
        "operations_and_debt": operations,
        "balance_sheet_cleanliness": clean_balance_sheet_checks(annual_metrics, operations, inc, annual[0]),
        "missing_information": [
            "market_size_and_cagr_require_external_research",
            "peer_comparison_requires_peer_list_or_industry_screen",
            "customer_concentration_may_require_annual_report_pdf_notes",
            "volume_price_split_often_not_available_in_standard_apis",
        ],
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(to_yaml(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
