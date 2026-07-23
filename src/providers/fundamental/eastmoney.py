"""东方财富结构化基本面 provider（stock_fundamental_snapshot 的公司/股东/股本/主营构成来源）。

非官方接口，无 SLA。A 股使用 `emweb.securities.eastmoney.com/PC_HSF10/{Section}/PageAjax`
返回 JSON：

- CompanySurvey：公司概况（jbzl 基本资料 + fxxg 发行上市）
- ShareholderResearch：股东研究（gdrs 户数 / sjkzr 实控人 / sdgd 十大股东 / sdltgd 十大流通股东）
- CapitalStockStructure：股本结构（gbjg 最新股本）
- BusinessAnalysis：经营分析（zygcfx 主营构成，MAINOP_TYPE 1=按行业 2=按产品 3=按地区）

与旧的文本版 F10 provider 不同，本 provider 返回结构化模型，数字为数字，
单位换算（亿元/百分数）在 provider 内完成。
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from src.errors import ErrorType, ProviderError
from src.schemas import (
    BusinessComposition,
    BusinessCompositionItem,
    ShareholderItem,
    Shareholders,
)
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol

HSF10_PAGE_AJAX = "https://emweb.securities.eastmoney.com/PC_HSF10/{section}/PageAjax"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://emweb.securities.eastmoney.com/",
}


class CompanySurvey(BaseModel):
    name: str | None = None
    full_name: str | None = None
    industry_sw: str | None = None
    industry_csrc: str | None = None
    trade_market: str | None = None
    chairman: str | None = None
    president: str | None = None
    secretary: str | None = None
    legal_person: str | None = None
    employees: float | None = None
    reg_address: str | None = None
    office_address: str | None = None
    website: str | None = None
    introduction: str | None = None
    business_scope: str | None = None
    founded_date: str | None = None
    listing_date: str | None = None


class CapitalStructure(BaseModel):
    total_shares: float | None = None
    limited_shares: float | None = None
    float_shares: float | None = None


class EastmoneyFundamentalProvider:
    name = "eastmoney"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_company_survey(self, symbol: NormalizedSymbol) -> CompanySurvey:
        payload = await self._fetch(symbol, "CompanySurvey")
        info = _first_row(payload.get("jbzl")) or {}
        listing = _first_row(payload.get("fxxg")) or {}
        if not info and not listing:
            raise _empty(self.name, "company survey")
        return CompanySurvey(
            name=_str(info.get("SECURITY_NAME_ABBR")),
            full_name=_str(info.get("ORG_NAME")),
            industry_sw=_str(info.get("EM2016")),
            industry_csrc=_str(info.get("INDUSTRYCSRC1")),
            trade_market=_str(info.get("TRADE_MARKET")),
            chairman=_str(info.get("CHAIRMAN")),
            president=_str(info.get("PRESIDENT")),
            secretary=_str(info.get("SECRETARY")),
            legal_person=_str(info.get("LEGAL_PERSON")),
            employees=_num(info.get("EMP_NUM")),
            reg_address=_str(info.get("REG_ADDRESS")),
            office_address=_str(info.get("ADDRESS")),
            website=_str(info.get("ORG_WEB")),
            introduction=_str(info.get("ORG_PROFILE")),
            business_scope=_str(info.get("BUSINESS_SCOPE")),
            founded_date=_date(listing.get("FOUND_DATE")),
            listing_date=_date(listing.get("LISTING_DATE")),
        )

    async def get_shareholders(self, symbol: NormalizedSymbol) -> Shareholders:
        payload = await self._fetch(symbol, "ShareholderResearch")
        gdrs = payload.get("gdrs") or []
        sjkzr = payload.get("sjkzr") or []
        sdgd = payload.get("sdgd") or []
        sdltgd = payload.get("sdltgd") or []
        if not (gdrs or sjkzr or sdgd or sdltgd):
            raise _empty(self.name, "shareholder research")
        latest_gdrs = gdrs[0] if gdrs else {}
        controller = sjkzr[0] if sjkzr else {}
        return Shareholders(
            holder_count=_num(latest_gdrs.get("HOLDER_TOTAL_NUM")),
            holder_count_date=_date(latest_gdrs.get("END_DATE")),
            holder_count_change_pct=_num(latest_gdrs.get("TOTAL_NUM_RATIO")),
            controller=_str(controller.get("HOLDER_NAME")),
            controller_ratio_pct=_num(controller.get("HOLD_RATIO")),
            top10_date=_date(sdgd[0].get("END_DATE")) if sdgd else None,
            top10=[_map_holder(row, ratio_key="HOLD_NUM_RATIO") for row in sdgd[:10]],
            top10_float=[_map_holder(row, ratio_key="FREE_HOLDNUM_RATIO") for row in sdltgd[:10]],
        )

    async def get_capital_structure(self, symbol: NormalizedSymbol) -> CapitalStructure:
        payload = await self._fetch(symbol, "CapitalStockStructure")
        row = _first_row(payload.get("gbjg"))
        if row is None:
            raise _empty(self.name, "capital structure")
        return CapitalStructure(
            total_shares=_num(row.get("TOTAL_SHARES")),
            limited_shares=_num(row.get("LIMITED_SHARES")),
            float_shares=_num(row.get("UNLIMITED_SHARES")),
        )

    async def get_business_composition(self, symbol: NormalizedSymbol) -> BusinessComposition:
        payload = await self._fetch(symbol, "BusinessAnalysis")
        rows = [row for row in (payload.get("zygcfx") or []) if isinstance(row, dict)]
        if not rows:
            raise _empty(self.name, "business composition")
        latest = max(str(row.get("REPORT_DATE") or "") for row in rows)
        current = [row for row in rows if str(row.get("REPORT_DATE") or "") == latest]
        return BusinessComposition(
            period=latest[:10] or None,
            by_industry=_composition_items(current, "1"),
            by_product=_composition_items(current, "2"),
            by_region=_composition_items(current, "3"),
        )

    async def _fetch(self, symbol: NormalizedSymbol, section: str) -> dict[str, Any]:
        return await get_json(
            self.client,
            HSF10_PAGE_AJAX.format(section=section),
            provider=self.name,
            params={"code": f"{symbol.exchange.upper()}{symbol.symbol}"},
            headers=DEFAULT_HEADERS,
        )


def _map_holder(row: dict[str, Any], *, ratio_key: str) -> ShareholderItem:
    return ShareholderItem(
        rank=_int(row.get("HOLDER_RANK")),
        name=_str(row.get("HOLDER_NAME")),
        holder_type=_str(row.get("HOLDER_TYPE")) or _str(row.get("SHARES_TYPE")),
        shares=_num(row.get("HOLD_NUM")),
        ratio_pct=_num(row.get(ratio_key)),
        # HOLD_NUM_CHANGE 可能是数字或 "不变"/"新进" 等文本，文本一律视为 None。
        change_shares=_num(row.get("HOLD_NUM_CHANGE")),
    )


def _composition_items(
    rows: list[dict[str, Any]],
    mainop_type: str,
) -> list[BusinessCompositionItem]:
    selected = [row for row in rows if str(row.get("MAINOP_TYPE")) == mainop_type]
    selected.sort(key=lambda row: (row.get("RANK") is None, row.get("RANK") or 0))
    return [
        BusinessCompositionItem(
            name=_str(row.get("ITEM_NAME")),
            revenue_yi=_round_yi(_num(row.get("MAIN_BUSINESS_INCOME"))),
            cost_yi=_round_yi(_num(row.get("MAIN_BUSINESS_COST"))),
            gross_profit_yi=_round_yi(_num(row.get("MAIN_BUSINESS_RPOFIT"))),
            gross_margin_pct=_round_pct(_num(row.get("GROSS_RPOFIT_RATIO"))),
            revenue_pct=_round_pct(_num(row.get("MBI_RATIO"))),
        )
        for row in selected
    ]


def _first_row(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


def _empty(provider: str, section: str) -> ProviderError:
    return ProviderError(
        error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
        provider=provider,
        message=f"Eastmoney returned no {section} rows.",
    )


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _date(value: Any) -> str | None:
    text = _str(value)
    return text[:10] if text else None


def _round_yi(value: float | None) -> float | None:
    # 元 -> 亿元，保留 4 位小数。
    return None if value is None else round(value / 1e8, 4)


def _round_pct(ratio: float | None) -> float | None:
    # 小数比率 -> 百分数，保留 2 位小数。
    return None if ratio is None else round(ratio * 100, 2)
