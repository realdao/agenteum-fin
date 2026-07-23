"""东方财富 F10 provider，替代 mootdx 在 VPS 上不稳定的 F10 通道。

非官方接口，无 SLA。A 股使用 `emweb.securities.eastmoney.com/PC_HSF10/{Section}/PageAjax`
返回 JSON。`financial_analysis` 走 datacenter-web 主要财务指标接口
（RPT_LICO_FN_CPD），`latest_notice` 走东方财富公告摘要接口（np-anotice-stock）。

字段名采用东方财富原始大写键名（如 SECUCODE、HOLDER_NAME）；解析时只取每个 section
中信息量最高、最稳定的子表，保留人类可读的中英字段标签。返回纯文本由 StockF10Service
截取 max_chars 后吐给大模型。
"""

from __future__ import annotations

from typing import Any

import httpx

from src.errors import ErrorType, ProviderError
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol

HSF10_PAGE_AJAX = "https://emweb.securities.eastmoney.com/PC_HSF10/{section}/PageAjax"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
NOTICE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://emweb.securities.eastmoney.com/",
}

HSF10_SECTIONS = {
    "company_profile": "CompanySurvey",
    "shareholders": "ShareholderResearch",
    "capital_structure": "CapitalStockStructure",
}

FINANCIAL_REPORT_NAME = "RPT_LICO_FN_CPD"


class EastmoneyF10Provider:
    name = "eastmoney"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_f10(self, symbol: NormalizedSymbol, section: str) -> str:
        if section in HSF10_SECTIONS:
            return await self._fetch_hsf10(symbol, section)
        if section == "financial_analysis":
            return await self._fetch_financial(symbol)
        if section == "latest_notice":
            return await self._fetch_notices(symbol)
        raise ProviderError(
            error_type=ErrorType.INVALID_REQUEST,
            provider=self.name,
            message=f"Unsupported F10 section: {section}",
        )

    def _hsf10_code(self, symbol: NormalizedSymbol) -> str:
        return f"{symbol.exchange.upper()}{symbol.symbol}"

    def _secucode(self, symbol: NormalizedSymbol) -> str:
        return f"{symbol.symbol}.{symbol.exchange.upper()}"

    async def _fetch_hsf10(self, symbol: NormalizedSymbol, section: str) -> str:
        url = HSF10_PAGE_AJAX.format(section=HSF10_SECTIONS[section])
        payload = await get_json(
            self.client,
            url,
            provider=self.name,
            params={"code": self._hsf10_code(symbol)},
            headers=DEFAULT_HEADERS,
        )
        return _format_hsf10(section, payload)

    async def _fetch_financial(self, symbol: NormalizedSymbol) -> str:
        payload = await get_json(
            self.client,
            DATACENTER_URL,
            provider=self.name,
            params={
                "reportName": FINANCIAL_REPORT_NAME,
                "columns": "ALL",
                "filter": f'(SECUCODE="{self._secucode(symbol)}")',
                "pageNumber": "1",
                "pageSize": "8",
                "sortColumns": "REPORTDATE",
                "sortTypes": "-1",
                "source": "HSF10",
                "client": "PC",
            },
            headers=DEFAULT_HEADERS,
        )
        rows = (payload.get("result") or {}).get("data") or []
        if not rows:
            raise ProviderError(
                error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                provider=self.name,
                message="Eastmoney returned no financial-analysis rows.",
                payload=payload,
            )
        return _format_financial(rows)

    async def _fetch_notices(self, symbol: NormalizedSymbol) -> str:
        payload = await get_json(
            self.client,
            NOTICE_URL,
            provider=self.name,
            params={
                "page_size": "15",
                "page_index": "1",
                "ann_type": "A",
                "stock_list": symbol.symbol,
                "f_node": "1",
                "s_node": "0",
            },
            headers=DEFAULT_HEADERS,
        )
        items = (payload.get("data") or {}).get("list") or []
        if not items:
            raise ProviderError(
                error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                provider=self.name,
                message="Eastmoney returned no latest notices.",
                payload=payload,
            )
        return _format_notices(items)


def _format_hsf10(section: str, payload: dict[str, Any]) -> str:
    if section == "company_profile":
        return _format_company(payload)
    if section == "shareholders":
        return _format_shareholders(payload)
    if section == "capital_structure":
        return _format_capital(payload)
    # 防御性兜底，正常不会触发。
    return _kv_block(section, payload)


def _format_company(payload: dict[str, Any]) -> str:
    info = _first_row(payload.get("jbzl"))
    listing = _first_row(payload.get("fxxg"))
    lines = ["公司概况（东方财富 F10）：", ""]
    if info:
        lines += [
            "基本资料：",
            f"- 证券代码：{_g(info, 'SECURITY_CODE')}",
            f"- 证券简称：{_g(info, 'SECURITY_NAME_ABBR')}",
            f"- 公司全称：{_g(info, 'ORG_NAME')}",
            f"- 英文名称：{_g(info, 'ORG_NAME_EN')}",
            f"- 曾用名：{_g(info, 'FORMERNAME') or '—'}",
            f"- 证券类型：{_g(info, 'SECURITY_TYPE')}",
            f"- 上市板块：{_g(info, 'TRADE_MARKET')}",
            f"- 申万行业：{_g(info, 'EM2016')}",
            f"- 证监会行业：{_g(info, 'INDUSTRYCSRC1')}",
            f"- 董事长：{_g(info, 'CHAIRMAN') or '—'}",
            f"- 总经理：{_g(info, 'PRESIDENT') or '—'}",
            f"- 董秘：{_g(info, 'SECRETARY') or '—'}",
            f"- 法人代表：{_g(info, 'LEGAL_PERSON') or '—'}",
            f"- 注册地址：{_g(info, 'REG_ADDRESS') or '—'}",
            f"- 办公地址：{_g(info, 'ADDRESS') or '—'}",
            f"- 注册资本(万元)：{_fmt_num(info.get('REG_CAPITAL'))}",
            f"- 员工人数：{_fmt_num(info.get('EMP_NUM') or '—')}",
            f"- 联系电话：{_g(info, 'ORG_TEL') or '—'}",
            f"- 邮箱：{_g(info, 'ORG_EMAIL') or '—'}",
            f"- 公司网址：{_g(info, 'ORG_WEB') or '—'}",
            "",
            "公司简介：",
            _g(info, "ORG_PROFILE") or "（无简介）",
            "",
            "经营范围：",
            _g(info, "BUSINESS_SCOPE") or "（无经营范围）",
        ]
    if listing:
        lines += [
            "",
            "发行相关：",
            f"- 成立日期：{_date(_g(listing, 'FOUND_DATE'))}",
            f"- 上市日期：{_date(_g(listing, 'LISTING_DATE'))}",
            f"- 发行价(元)：{_fmt_num(listing.get('ISSUE_PRICE'))}",
            f"- 发行方式：{_g(listing, 'ISSUE_WAY') or '—'}",
            f"- 发行量(股)：{_fmt_num(listing.get('TOTAL_ISSUE_NUM'))}",
            f"- 募集净额(元)：{_fmt_num(listing.get('NET_RAISE_FUNDS'))}",
            f"- 首日开盘价(元)：{_fmt_num(listing.get('OPEN_PRICE'))}",
            f"- 首日收盘价(元)：{_fmt_num(listing.get('CLOSE_PRICE'))}",
            f"- 首日最高价(元)：{_fmt_num(listing.get('HIGH_PRICE'))}",
            f"- 发行市盈率：{_fmt_num(listing.get('AFTER_ISSUE_PE'))}",
        ]
    if not info and not listing:
        return "公司概况（东方财富 F10）：无数据"
    return "\n".join(lines)


def _format_shareholders(payload: dict[str, Any]) -> str:
    lines = ["股东研究（东方财富 F10）：", ""]
    holders = payload.get("gdrs") or []
    if holders:
        latest = holders[0]
        lines += [
            "股东户数：",
            f"- 截止日期：{_date(_g(latest, 'END_DATE'))}",
            f"- 股东户数(户)：{_fmt_num(latest.get('HOLDER_TOTAL_NUM'))}",
            f"- 较上期变化比例(%)：{_fmt_num(latest.get('TOTAL_NUM_RATIO'))}",
            f"- 户均流通股：{_fmt_num(latest.get('AVG_FREE_SHARES'))}",
            f"- 户均持股市值(元)：{_fmt_num(latest.get('AVG_HOLD_AMT'))}",
            f"- 持股集中度：{_fmt_num(latest.get('HOLD_FOCUS'))}",
        ]
    controllers = payload.get("sjkzr") or []
    if controllers:
        cnt = controllers[0]
        lines += [
            "",
            "实际控制人：",
            f"- 控制人：{_g(cnt, 'HOLDER_NAME') or '—'}",
            f"- 持股比例(%)：{_fmt_num(cnt.get('HOLD_RATIO'))}",
        ]
    shareholders = payload.get("sdgd") or []
    if shareholders:
        latest_date = _g(shareholders[0], "END_DATE") or ""
        lines += ["", f"十大股东（截止 {latest_date}）："]
        for holder in shareholders[:10]:
            lines.append(
                f"- 排名{_fmt_num(holder.get('HOLDER_RANK'))}："
                f"{_g(holder, 'HOLDER_NAME')} "
                f"({_g(holder, 'HOLDER_TYPE') or _g(holder, 'SHARES_TYPE') or '—'}) "
                f"持股{_fmt_num(holder.get('HOLD_NUM'))}股 "
                f"占比{_fmt_num(holder.get('HOLD_NUM_RATIO'))}% "
                f"变动{_fmt_num(holder.get('HOLD_NUM_CHANGE'))}股"
            )
    floaters = payload.get("sdltgd") or []
    if floaters:
        latest_date = _g(floaters[0], "END_DATE") or ""
        lines += ["", f"十大流通股东（截止 {latest_date}）："]
        for holder in floaters[:10]:
            lines.append(
                f"- 排名{_fmt_num(holder.get('HOLDER_RANK'))}："
                f"{_g(holder, 'HOLDER_NAME')} "
                f"持股{_fmt_num(holder.get('HOLD_NUM'))}股 "
                f"流通占比{_fmt_num(holder.get('FREE_HOLDNUM_RATIO'))}% "
                f"变动{_fmt_num(holder.get('HOLD_NUM_CHANGE'))}股"
            )
    if not holders and not shareholders and not floaters and not controllers:
        return "股东研究（东方财富 F10）：无数据"
    return "\n".join(lines)


def _format_capital(payload: dict[str, Any]) -> str:
    lines = ["股本结构（东方财富 F10）：", ""]
    structure = _first_row(payload.get("gbjg"))
    if structure:
        lines += [
            "最新股本结构：",
            f"- 总股本(股)：{_fmt_num(structure.get('TOTAL_SHARES'))}",
            f"- 限售股(股)：{_fmt_num(structure.get('LIMITED_SHARES'))}",
            f"- 流通股(股)：{_fmt_num(structure.get('UNLIMITED_SHARES'))}",
            f"- 已上市流通A股(股)：{_fmt_num(structure.get('LISTED_A_SHARES'))}",
            f"- 限售流通占比(%)：{_fmt_num(structure.get('LIMITED_SHARES_RATIO'))}",
            f"- 流通占比(%)：{_fmt_num(structure.get('UNLIMITED_SHARES_RATIO'))}",
            f"- 上市A股占比(%)：{_fmt_num(structure.get('LISTED_SHARES_RATIO'))}",
        ]
    history = payload.get("lngbbd") or []
    if history:
        lines += ["", f"股本变动历史（最近 {min(len(history), 10)} 次）："]
        for row in history[:10]:
            lines.append(
                f"- {_date(_g(row, 'END_DATE'))}："
                f"总股本{_fmt_num(row.get('TOTAL_SHARES'))}股 "
                f"流通A股{_fmt_num(row.get('LISTED_A_SHARES'))}股 "
                f"（{_g(row, 'CHANGE_REASON') or '变更'}）"
            )
    if not structure and not history:
        return "股本结构（东方财富 F10）：无数据"
    return "\n".join(lines)


# fmt 用字符串标识，dispatch 在 _format_financial 内查表；
# 这样常量在 import-time 不会触发对 _date/_fmt_num 的早解析，顺序无关。
_FINANCIAL_COLUMNS = [
    ("报告期", "REPORTDATE", "date"),
    ("营业收入(元)", "TOTAL_OPERATE_INCOME", "num"),
    ("营收同比(%)", "YSTZ", "num"),
    ("归母净利润(元)", "PARENT_NETPROFIT", "num"),
    ("归母净利同比(%)", "SJLTZ", "num"),
    ("基本EPS(元)", "BASIC_EPS", "num"),
    ("扣非EPS(元)", "DEDUCT_BASIC_EPS", "num"),
    ("每股净资产(元)", "BPS", "num"),
    ("每股经营现金流(元)", "MGJYXJJE", "num"),
    ("销售毛利率(%)", "XSMLL", "num"),
    ("加权ROE(%)", "WEIGHTAVG_ROE", "num"),
    ("分红方案", "ASSIGNDSCRPT", "num"),
]

_FINANCIAL_FMT = {"num": lambda v: _fmt_num(v), "date": lambda v: _date(v)}


def _format_financial(rows: list[Any]) -> str:
    lines = ["财务分析（东方财富 F10 主要财务指标）：", ""]
    lines.append("| " + " | ".join(label for label, _, _ in _FINANCIAL_COLUMNS) + " |")
    lines.append("| " + " | ".join(["---"] * len(_FINANCIAL_COLUMNS)) + " |")
    for row in rows[:8]:
        cells = []
        for _, key, fmt_name in _FINANCIAL_COLUMNS:
            value = row.get(key) if isinstance(row, dict) else None
            cells.append(_FINANCIAL_FMT[fmt_name](value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _format_notices(items: list[Any]) -> str:
    lines = ["最新公告（东方财富 F10）：", ""]
    for item in items[:15]:
        title = _g(item, "title") or _g(item, "title_ch") or _g(item, "art_code") or "—"
        notice_date = (_g(item, "notice_date") or "")[:10]
        columns = item.get("columns") or []
        col_name = next(
            (
                col.get("column_name")
                for col in columns
                if isinstance(col, dict) and col.get("column_name")
            ),
            "",
        )
        tail = f"（{col_name}）" if col_name else ""
        lines.append(f"- {notice_date or '—'}：{title}{tail}")
    return "\n".join(lines)


def _first_row(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


def _g(obj: dict[str, Any] | None, key: str) -> str | None:
    if obj is None:
        return None
    value = obj.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fmt_num(value: Any) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "—"
    if number == int(number):
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".") or "0"


def _date(value: str | None) -> str:
    if not value:
        return "—"
    return value[:10]


def _len(value: Any) -> int:
    return len(value) if isinstance(value, (list, dict, str)) else 0


def _kv_block(title: str, payload: dict[str, Any]) -> str:
    lines = [f"{title}（东方财富 F10）：", ""]
    for key, value in payload.items():
        if isinstance(value, list) and value:
            lines.append(f"- {key}: 列表({_len(value)})")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)