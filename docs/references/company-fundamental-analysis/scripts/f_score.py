from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)


def clean_code(code: str) -> str:
    digits = re.sub(r"\D", "", code)
    return digits.zfill(6)[-6:]


def market_prefix(code: str) -> str:
    return "sh" if code.startswith(("6", "9")) else ("bj" if code.startswith("8") else "sz")


def num(value: Any) -> float | None:
    if value is None or value == "" or str(value).lower() in {"nan", "none", "--", "false"}:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def div(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def round_or_none(x: float | None, ndigits: int = 6) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), ndigits)


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


def value(row: pd.Series | None, name: str) -> float | None:
    return num(row.get(name)) if row is not None else None


def score_item(name: str, passed: bool | None, current: Any, previous: Any, rule: str) -> dict[str, Any]:
    return {
        "name": name,
        "score": 1 if passed else 0,
        "passed": passed,
        "current": current,
        "previous": previous,
        "rule": rule,
    }


def band(score: int) -> str:
    if score <= 3:
        return "weak"
    if score <= 6:
        return "neutral"
    return "strong"


def compute(code: str, period: str | None = None) -> dict[str, Any]:
    abs_df = get_abstract(code)
    periods = annual_periods(abs_df)
    if not periods:
        raise RuntimeError("No annual periods found")
    current = period or periods[0]
    if current not in periods:
        raise RuntimeError(f"Period {current} not found; available: {periods[:8]}")
    idx = periods.index(current)
    if idx + 1 >= len(periods):
        raise RuntimeError("Previous annual period not available")
    previous = periods[idx + 1]

    bs = ak.stock_financial_report_sina(stock=f"{market_prefix(code)}{code}", symbol="资产负债表")
    inc = ak.stock_financial_report_sina(stock=f"{market_prefix(code)}{code}", symbol="利润表")
    cur_bs = row_by_period(bs, current)
    prev_bs = row_by_period(bs, previous)
    cur_inc = row_by_period(inc, current)
    prev_inc = row_by_period(inc, previous)

    cur_assets = value(cur_bs, "资产总计")
    prev_assets = value(prev_bs, "资产总计")
    avg_assets = div((cur_assets or 0) + (prev_assets or 0), 2)

    prev_prev_period = periods[idx + 2] if idx + 2 < len(periods) else None
    prev_prev_bs = row_by_period(bs, prev_prev_period) if prev_prev_period else None
    prev_avg_assets = div((prev_assets or 0) + (value(prev_prev_bs, "资产总计") or 0), 2) if prev_prev_bs is not None else prev_assets

    cur_deducted = metric(abs_df, "扣非净利润", current)
    prev_deducted = metric(abs_df, "扣非净利润", previous)
    cur_net = metric(abs_df, "归母净利润", current)
    cur_ocf = metric(abs_df, "经营现金流量净额", current)
    cur_revenue = metric(abs_df, "营业总收入", current)
    prev_revenue = metric(abs_df, "营业总收入", previous)

    cur_roa = div(cur_deducted, avg_assets)
    prev_roa = div(prev_deducted, prev_avg_assets)
    cur_cfo_assets = div(cur_ocf, avg_assets)

    cur_non_current_liab = value(cur_bs, "非流动负债合计")
    prev_non_current_liab = value(prev_bs, "非流动负债合计")
    cur_long_debt_ratio = div(cur_non_current_liab, cur_assets)
    prev_long_debt_ratio = div(prev_non_current_liab, prev_assets)

    cur_current_ratio = div(value(cur_bs, "流动资产合计"), value(cur_bs, "流动负债合计"))
    prev_current_ratio = div(value(prev_bs, "流动资产合计"), value(prev_bs, "流动负债合计"))

    cur_share_capital = value(cur_bs, "实收资本(或股本)")
    prev_share_capital = value(prev_bs, "实收资本(或股本)")

    cur_gross_margin = div((value(cur_inc, "营业收入") or 0) - (value(cur_inc, "营业成本") or 0), value(cur_inc, "营业收入"))
    prev_gross_margin = div((value(prev_inc, "营业收入") or 0) - (value(prev_inc, "营业成本") or 0), value(prev_inc, "营业收入"))

    cur_asset_turnover = div(cur_revenue, avg_assets)
    prev_asset_turnover = div(prev_revenue, prev_avg_assets)

    items = [
        score_item("deducted_roa_positive", cur_roa is not None and cur_roa > 0, round_or_none(cur_roa), None, "deducted_net_profit / avg_total_assets > 0"),
        score_item("operating_cash_flow_positive", cur_ocf is not None and cur_ocf > 0, cur_ocf, None, "operating_cash_flow > 0"),
        score_item("deducted_roa_improved", cur_roa is not None and prev_roa is not None and cur_roa > prev_roa, round_or_none(cur_roa), round_or_none(prev_roa), "current deducted ROA > previous deducted ROA"),
        score_item("cash_flow_exceeds_net_profit", cur_ocf is not None and cur_net is not None and cur_ocf > cur_net, cur_ocf, cur_net, "operating_cash_flow > net_profit"),
        score_item("long_debt_ratio_declined", cur_long_debt_ratio is not None and prev_long_debt_ratio is not None and cur_long_debt_ratio < prev_long_debt_ratio, round_or_none(cur_long_debt_ratio), round_or_none(prev_long_debt_ratio), "non_current_liabilities / total_assets declined"),
        score_item("current_ratio_improved", cur_current_ratio is not None and prev_current_ratio is not None and cur_current_ratio > prev_current_ratio, round_or_none(cur_current_ratio), round_or_none(prev_current_ratio), "current_ratio improved"),
        score_item("no_share_issuance", cur_share_capital is not None and prev_share_capital is not None and cur_share_capital <= prev_share_capital, cur_share_capital, prev_share_capital, "share capital did not increase"),
        score_item("gross_margin_improved", cur_gross_margin is not None and prev_gross_margin is not None and cur_gross_margin > prev_gross_margin, round_or_none(cur_gross_margin), round_or_none(prev_gross_margin), "gross_margin improved"),
        score_item("asset_turnover_improved", cur_asset_turnover is not None and prev_asset_turnover is not None and cur_asset_turnover > prev_asset_turnover, round_or_none(cur_asset_turnover), round_or_none(prev_asset_turnover), "asset_turnover improved"),
    ]
    total = sum(item["score"] for item in items)
    return {
        "meta": {
            "code": code,
            "period": current,
            "previous_period": previous,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": "piotroski_f_score_a_share_adapted",
        },
        "score": {
            "total": total,
            "max": 9,
            "band": band(total),
        },
        "components": {
            "profitability": items[:4],
            "leverage_liquidity": items[4:7],
            "operating_efficiency": items[7:],
        },
        "raw_metrics": {
            "deducted_roa": round_or_none(cur_roa),
            "previous_deducted_roa": round_or_none(prev_roa),
            "operating_cash_flow_to_assets": round_or_none(cur_cfo_assets),
            "long_debt_ratio": round_or_none(cur_long_debt_ratio),
            "previous_long_debt_ratio": round_or_none(prev_long_debt_ratio),
            "current_ratio": round_or_none(cur_current_ratio),
            "previous_current_ratio": round_or_none(prev_current_ratio),
            "gross_margin": round_or_none(cur_gross_margin),
            "previous_gross_margin": round_or_none(prev_gross_margin),
            "asset_turnover": round_or_none(cur_asset_turnover),
            "previous_asset_turnover": round_or_none(prev_asset_turnover),
        },
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
    parser.add_argument("--period", help="Annual period such as 20251231. Defaults to latest annual period.")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    args = parser.parse_args()

    result = compute(clean_code(args.code), args.period)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(to_yaml(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
