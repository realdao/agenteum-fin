"""akshare 财务数据源（stock_fundamental_snapshot 的财务摘要与报表来源）。

A 股（移植自 workspace 技能 company-fundamental-analysis 的取数层）：

- `stock_financial_abstract`：同花顺财务摘要，按报告期给出营业总收入/归母/扣非/
  净资产/经营现金流/商誉等关键指标（扣非净利润的唯一稳定来源）。
- `stock_financial_report_sina`：新浪财经资产负债表/利润表，中文科目列。

港股（东财港股接口族，字段与口径经 playground/hk_fundamental_probe.py 实测）：

- `stock_financial_hk_analysis_indicator_em`：主要指标（年度/报告期各 9 期），
  含营收/归母/毛利率/净利率/ROE(加权)/ROA/YoY/负债率/流动比率，币种 HKD。
- `stock_financial_hk_report_em`：三大报表长表（REPORT_DATE + STD_ITEM_NAME + AMOUNT），
  IFRS 科目口径。
- `stock_hk_company_profile_em` / `stock_hk_security_profile_em`：公司与证券资料。

akshare 是同步 requests 实现，统一用 `asyncio.to_thread` 包装为异步接口；
akshare 在模块级 import 时开销较大，因此在使用时才惰性导入。
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
import requests
from pydantic import BaseModel

from src.errors import ErrorType, ProviderError
from src.utils.symbols import NormalizedSymbol

_PERIOD_PATTERN = re.compile(r"\d{8}")

HkReportType = Literal["annual", "report"]

_HK_INDICATOR_BY_TYPE: dict[HkReportType, str] = {
    "annual": "年度",
    "report": "报告期",
}


class HKCompanyInfo(BaseModel):
    """港股公司与证券资料的合并视图（东财）。"""

    name: str | None = None
    full_name: str | None = None
    industry: str | None = None
    chairman: str | None = None
    secretary: str | None = None
    employees: float | None = None
    reg_address: str | None = None
    office_address: str | None = None
    website: str | None = None
    email: str | None = None
    auditor: str | None = None
    introduction: str | None = None
    founded_date: str | None = None
    listing_date: str | None = None
    exchange: str | None = None
    board: str | None = None


class AkshareFinancialsProvider:
    name = "akshare"

    async def get_financial_abstract(
        self,
        symbol: NormalizedSymbol,
    ) -> dict[str, dict[str, Any]]:
        """返回 {指标名: {期间(YYYYMMDD): 原始值}}；同名指标跨分类重复时保留首次出现。"""
        df = await self._run(lambda ak: ak.stock_financial_abstract(symbol.symbol))
        if df is None or df.empty:
            raise _empty(self.name, "financial abstract")
        indexed = df.set_index("指标")
        periods = [c for c in indexed.columns if _PERIOD_PATTERN.fullmatch(str(c))]
        abstract: dict[str, dict[str, Any]] = {}
        for name, row in indexed.iterrows():
            key = str(name)
            if key in abstract:
                continue
            abstract[key] = {str(period): _scalar(row.get(period)) for period in periods}
        return abstract

    async def get_balance_sheet(self, symbol: NormalizedSymbol) -> list[dict[str, Any]]:
        return await self._sina_report(symbol, "资产负债表")

    async def get_income_statement(self, symbol: NormalizedSymbol) -> list[dict[str, Any]]:
        return await self._sina_report(symbol, "利润表")

    async def _sina_report(
        self,
        symbol: NormalizedSymbol,
        report_name: str,
    ) -> list[dict[str, Any]]:
        stock = f"{symbol.exchange}{symbol.symbol}"
        df = await self._run(
            lambda ak: ak.stock_financial_report_sina(stock=stock, symbol=report_name)
        )
        if df is None or df.empty:
            raise _empty(self.name, f"sina {report_name}")
        return [
            {str(key): _scalar(value) for key, value in row.items()}
            for row in df.to_dict("records")
        ]

    # ------------------------------------------------------------------ 港股

    async def get_hk_company_info(self, symbol: NormalizedSymbol) -> HKCompanyInfo:
        """合并东财港股公司资料与证券资料（两次 akshare 调用，失败其一即整体失败）。"""
        profile_df, security_df = await asyncio.gather(
            self._run(lambda ak: ak.stock_hk_company_profile_em(symbol=symbol.symbol)),
            self._run(lambda ak: ak.stock_hk_security_profile_em(symbol=symbol.symbol)),
        )
        if (profile_df is None or profile_df.empty) and (
            security_df is None or security_df.empty
        ):
            raise _empty(self.name, "HK company info")
        profile = _first_record(profile_df)
        security = _first_record(security_df)
        return HKCompanyInfo(
            name=_str_or_none(security.get("证券简称")) or _str_or_none(profile.get("公司名称")),
            full_name=_str_or_none(profile.get("公司名称")),
            industry=_str_or_none(profile.get("所属行业")),
            chairman=_str_or_none(profile.get("董事长")),
            secretary=_str_or_none(profile.get("公司秘书")),
            employees=_num_or_none(profile.get("员工人数")),
            reg_address=_str_or_none(profile.get("注册地址")),
            office_address=_str_or_none(profile.get("办公地址")),
            website=_str_or_none(profile.get("公司网址")),
            email=_str_or_none(profile.get("E-MAIL")),
            auditor=_str_or_none(profile.get("核数师")),
            introduction=_str_or_none(profile.get("公司介绍")),
            founded_date=_str_or_none(profile.get("公司成立日期")),
            listing_date=_date_or_none(security.get("上市日期")),
            exchange=_str_or_none(security.get("交易所")),
            board=_str_or_none(security.get("板块")),
        )

    async def get_hk_main_indicators_annual(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_main_indicators(symbol, "annual")

    async def get_hk_main_indicators_report(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_main_indicators(symbol, "report")

    async def _hk_main_indicators(
        self,
        symbol: NormalizedSymbol,
        report_type: HkReportType,
    ) -> list[dict[str, Any]]:
        df = await self._run(
            lambda ak: ak.stock_financial_hk_analysis_indicator_em(
                symbol=symbol.symbol,
                indicator=_HK_INDICATOR_BY_TYPE[report_type],
            )
        )
        if df is None or df.empty:
            raise _empty(self.name, f"HK main indicators ({report_type})")
        return _records(df)

    async def get_hk_balance_sheet_annual(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_statement(symbol, "资产负债表", "annual")

    async def get_hk_balance_sheet_report(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_statement(symbol, "资产负债表", "report")

    async def get_hk_income_statement_annual(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_statement(symbol, "利润表", "annual")

    async def get_hk_cash_flow_annual(
        self,
        symbol: NormalizedSymbol,
    ) -> list[dict[str, Any]]:
        return await self._hk_statement(symbol, "现金流量表", "annual")

    async def _hk_statement(
        self,
        symbol: NormalizedSymbol,
        report_name: str,
        report_type: HkReportType,
    ) -> list[dict[str, Any]]:
        """东财港股三大报表，长表记录（REPORT_DATE / STD_ITEM_NAME / AMOUNT）。"""
        df = await self._run(
            lambda ak: ak.stock_financial_hk_report_em(
                stock=symbol.symbol,
                symbol=report_name,
                indicator=_HK_INDICATOR_BY_TYPE[report_type],
            )
        )
        if df is None or df.empty:
            raise _empty(self.name, f"HK {report_name} ({report_type})")
        return _records(df)

    async def _run(self, work: Callable[[Any], Any]) -> Any:
        try:
            import akshare as ak
        except ImportError as exc:  # pragma: no cover - akshare 是声明依赖
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider=self.name,
                message="akshare is not installed; run 'uv sync'.",
            ) from exc
        try:
            return await asyncio.to_thread(work, ak)
        except Exception as exc:
            raise _classify(exc, self.name) from exc


def _empty(provider: str, what: str) -> ProviderError:
    return ProviderError(
        error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
        provider=provider,
        message=f"akshare returned an empty {what}.",
    )


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _scalar(value) for key, value in row.items()}
        for row in df.to_dict("records")
    ]


def _first_record(df: pd.DataFrame | None) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    return {str(key): _scalar(value) for key, value in df.iloc[0].to_dict().items()}


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _num_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _date_or_none(value: Any) -> str | None:
    text = _str_or_none(value)
    return text[:10] if text else None


def _classify(exc: Exception, provider: str) -> ProviderError:
    if isinstance(exc, requests.exceptions.Timeout):
        return ProviderError(
            error_type=ErrorType.TIMEOUT,
            provider=provider,
            message=str(exc),
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return ProviderError(
            error_type=ErrorType.NETWORK,
            provider=provider,
            message=str(exc),
        )
    return ProviderError(
        error_type=ErrorType.PROVIDER_ERROR,
        provider=provider,
        message=str(exc)[:300],
    )


def _scalar(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001 - numpy 标量转换失败时保留原值
            pass
    return value
