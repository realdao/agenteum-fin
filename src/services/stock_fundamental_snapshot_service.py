"""stock_fundamental_snapshot 的编排服务：一次调用聚合七个基本面维度。

设计原则（见 docs/stock-f10-refactor-plan-20260723.md §3.1）：

- 一次调用默认全量，`sections` 按需裁剪；
- 衍生指标（TTM、扣非、YoY、DuPont、负债率、有息负债）服务端算好；
- 块级降级：任一 provider 失败只影响依赖它的 block（block=null 且进 missing），
  不拖垮整次调用；缺失字段为 null，禁止编造；
- 港股暂未支持：不抛错，全部 block 置空并在 missing 中显式标注替代路径。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import (
    SNAPSHOT_SECTIONS,
    BalanceSheetFlags,
    FundamentalSnapshotData,
    FundamentalSnapshotRequest,
    FundamentalSnapshotResponse,
    GrowthPeriod,
    MissingItem,
    OperationsSolvencyPeriod,
    Profitability,
    ProfitabilityPeriod,
    QuoteValuation,
    SnapshotMeta,
    SnapshotProfile,
)
from src.services import fundamental_metrics as fm
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import NormalizedSymbol, normalize_symbol

# 数据源 -> (service 属性名, provider 方法名, 未配置时的 provider 标签)
_SOURCE_SPECS: dict[str, tuple[str, str, str]] = {
    "survey": ("profile_provider", "get_company_survey", "eastmoney"),
    "shareholders": ("profile_provider", "get_shareholders", "eastmoney"),
    "capital": ("profile_provider", "get_capital_structure", "eastmoney"),
    "composition": ("profile_provider", "get_business_composition", "eastmoney"),
    "quote": ("quote_provider", "get_profiles", "tencent"),
    "abstract": ("financials_provider", "get_financial_abstract", "akshare"),
    "balance_sheet": ("financials_provider", "get_balance_sheet", "akshare"),
    "income_statement": ("financials_provider", "get_income_statement", "akshare"),
}

# block -> 依赖的全部数据源 / 硬依赖数据源（硬依赖失败则整块降级；
# balance_sheet_flags 无硬依赖，任一源成功即产出）
_BLOCK_SOURCES: dict[str, tuple[str, ...]] = {
    "meta": ("survey", "capital"),
    "profile": ("survey", "shareholders"),
    "business_composition": ("composition",),
    "quote_valuation": ("quote", "abstract"),
    "profitability": ("abstract", "balance_sheet", "income_statement"),
    "growth": ("abstract",),
    "operations_solvency": ("balance_sheet", "abstract"),
    "balance_sheet_flags": ("income_statement", "balance_sheet", "abstract"),
    "shareholders": ("shareholders",),
}

_BLOCK_HARD_SOURCES: dict[str, tuple[str, ...]] = {
    "meta": ("survey",),
    "profile": ("survey",),
    "business_composition": ("composition",),
    "quote_valuation": ("quote",),
    "profitability": ("abstract",),
    "growth": ("abstract",),
    "operations_solvency": ("balance_sheet",),
    "balance_sheet_flags": (),
    "shareholders": ("shareholders",),
}

_STATIC_MISSING = [
    MissingItem(
        item="customer_concentration",
        reason="标准数据接口不披露客户/供应商集中度。",
        hint="查阅年报附注，或用 iwencai_query(domain=business) 查询客户供应商信息。",
    ),
    MissingItem(
        item="volume_price_split",
        reason="标准数据接口无量价拆分数据。",
        hint="查阅年报经营讨论与分析章节或卖方研报。",
    ),
    MissingItem(
        item="market_size_and_cagr",
        reason="市场规模与行业增速属于研究层数据。",
        hint="用 iwencai_query(domain=industry) 或外部行业研究补充。",
    ),
    MissingItem(
        item="peer_comparison",
        reason="同业对比需要标的列表与截面数据，不在单票快照内完成。",
        hint="用 iwencai_query(domain=astock/industry) 做同业截面筛选。",
    ),
    MissingItem(
        item="industry_chain_position",
        reason="产业链上下游定位为定性研究内容，无结构化数据源。",
        hint="参考 profile.business_scope、business_composition 与研报综合判断。",
    ),
]

_NOTES = [
    "金额单位为亿元（CNY），股本与持股数单位为股，比率为百分数；"
    "字段为 null 表示数据源未披露或无法计算，不做估算。",
    "TTM=最新报告期+上年年报-上年同期；pe_ttm_calculated/pe_ttm_deducted/ps_ttm "
    "由服务端按总市值自算，与行情源 pe_ttm 口径可能不同。",
    "盈利质量判断优先使用扣非净利润（deducted_*）口径。",
    "ROE/ROA 为期末口径（净利润/期末净资产、净利润/期末总资产），非加权平均。",
    "receivable_days_simple=应收账款/营业总收入×365，仅年报期计算。",
    "有息负债=短期借款+长期借款+应付债券+一年内到期的非流动负债。",
    "profitability.latest_quarter 为年初至报告期累计口径。",
]

_HK_NOTE = (
    "港股基本面快照暂未支持（P1 规划中）；过渡期可使用 wind-mcp 的 "
    "get_stock_basicinfo / get_stock_fundamentals 获取港股基本面数据。"
)

_HK_HINT = "使用 wind-mcp get_stock_basicinfo / get_stock_fundamentals 补充。"


class StockFundamentalSnapshotService:
    def __init__(
        self,
        *,
        profile_provider: Any,
        financials_provider: Any,
        quote_provider: Any,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.profile_provider = profile_provider
        self.financials_provider = financials_provider
        self.quote_provider = quote_provider
        self.retry_policy = retry_policy or RetryPolicy()

    async def get_snapshot(
        self,
        request: FundamentalSnapshotRequest,
    ) -> FundamentalSnapshotResponse:
        symbol = normalize_symbol(request.symbol)
        if symbol.market != "a_share":
            return self._market_not_supported(symbol)
        sections = (
            list(SNAPSHOT_SECTIONS) if "all" in request.sections else request.sections
        )
        needed_sources = {
            source for block in sections for source in _BLOCK_SOURCES[block]
        }
        values, errors = await self._fetch_sources(symbol, needed_sources)

        data = FundamentalSnapshotData(symbol=symbol)
        missing: list[MissingItem] = []
        providers: dict[str, list[str]] = {}
        for block in SNAPSHOT_SECTIONS:
            if block not in sections:
                continue
            failure = self._block_failure(block, errors)
            if failure is not None:
                missing.append(failure)
                continue
            setattr(data, block, self._build_block(block, symbol, values, request))
            providers[block] = sorted(
                {
                    self._provider_name(source)
                    for source in _BLOCK_SOURCES[block]
                    if source in values
                }
            )
        data.providers = providers
        data.missing = [*missing, *_STATIC_MISSING]
        data.notes = list(_NOTES)
        return FundamentalSnapshotResponse(
            status="ok",
            provider="multi",
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=data,
        )

    # ------------------------------------------------------------------ fetch

    async def _fetch_sources(
        self,
        symbol: NormalizedSymbol,
        sources: set[str],
    ) -> tuple[dict[str, Any], dict[str, ProviderError]]:
        results = await asyncio.gather(
            *(self._fetch_one(symbol, source) for source in sorted(sources))
        )
        values: dict[str, Any] = {}
        errors: dict[str, ProviderError] = {}
        for source, result in results:
            if isinstance(result, ProviderError):
                errors[source] = result
            else:
                values[source] = result
        return values, errors

    async def _fetch_one(
        self,
        symbol: NormalizedSymbol,
        source: str,
    ) -> tuple[str, Any]:
        attr, method_name, default_name = _SOURCE_SPECS[source]
        provider = getattr(self, attr)
        if provider is None:
            return source, ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider=default_name,
                message=f"Fundamental source '{source}' is not configured.",
            )
        method = getattr(provider, method_name)
        try:
            result = await logged_provider_call(
                operation=f"stock_fundamental_snapshot.{source}",
                provider=provider.name,
                symbol=symbol,
                fallback_count=0,
                call=lambda: run_with_retries(
                    lambda: self._call_source(method, symbol, source),
                    policy=self.retry_policy,
                ),
            )
        except ProviderError as exc:
            return source, exc
        except Exception as exc:  # 防御：解析异常只降级对应源，不拖垮整次调用
            return source, ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=provider.name,
                message=str(exc)[:300],
            )
        return source, result

    @staticmethod
    async def _call_source(method: Any, symbol: NormalizedSymbol, source: str) -> Any:
        if source == "quote":
            profiles = await method([symbol])
            if not profiles:
                raise ProviderError(
                    error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                    provider="tencent",
                    message="Tencent quote returned no data for this symbol.",
                )
            return profiles[0]
        return await method(symbol)

    # ----------------------------------------------------------------- blocks

    def _block_failure(
        self,
        block: str,
        errors: dict[str, ProviderError],
    ) -> MissingItem | None:
        hard = _BLOCK_HARD_SOURCES[block]
        failed_hard = [source for source in hard if source in errors]
        if failed_hard:
            exc = errors[failed_hard[0]]
            return MissingItem(item=block, reason=_reason(exc))
        if not hard and all(source in errors for source in _BLOCK_SOURCES[block]):
            failed = next(source for source in _BLOCK_SOURCES[block] if source in errors)
            return MissingItem(item=block, reason=_reason(errors[failed]))
        return None

    def _build_block(
        self,
        block: str,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> Any:
        builder = getattr(self, f"_build_{block}")
        return builder(symbol, values, request)

    def _build_meta(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: Any,
    ) -> SnapshotMeta:
        survey = values.get("survey")
        capital = values.get("capital")
        return SnapshotMeta(
            name=survey.name if survey else None,
            full_name=survey.full_name if survey else None,
            market=symbol.market,
            exchange=symbol.exchange,
            industry_sw=survey.industry_sw if survey else None,
            industry_csrc=survey.industry_csrc if survey else None,
            currency="CNY",
            listing_date=survey.listing_date if survey else None,
            total_shares=capital.total_shares if capital else None,
            float_shares=capital.float_shares if capital else None,
            limited_shares=capital.limited_shares if capital else None,
        )

    def _build_profile(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: Any,
    ) -> SnapshotProfile:
        survey = values.get("survey")
        holders = values.get("shareholders")
        return SnapshotProfile(
            introduction=survey.introduction if survey else None,
            business_scope=survey.business_scope if survey else None,
            founded_date=survey.founded_date if survey else None,
            listing_date=survey.listing_date if survey else None,
            chairman=survey.chairman if survey else None,
            president=survey.president if survey else None,
            secretary=survey.secretary if survey else None,
            legal_person=survey.legal_person if survey else None,
            employees=survey.employees if survey else None,
            reg_address=survey.reg_address if survey else None,
            office_address=survey.office_address if survey else None,
            website=survey.website if survey else None,
            controller=holders.controller if holders else None,
            controller_ratio_pct=holders.controller_ratio_pct if holders else None,
        )

    def _build_business_composition(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: Any,
    ) -> Any:
        return values["composition"]

    def _build_quote_valuation(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: Any,
    ) -> QuoteValuation:
        quote = values["quote"]
        abstract = values.get("abstract") or {}
        ttm = fm.build_ttm_valuation(
            abstract,
            fm.all_periods(abstract),
            quote.market_cap,
        )
        return QuoteValuation(
            price=quote.price,
            market_cap_yi=fm.round_or_none(fm.yi(quote.market_cap), 4),
            float_market_cap_yi=fm.round_or_none(fm.yi(quote.float_market_cap), 4),
            pe_ttm=quote.pe_ttm,
            pe_static=quote.pe_static,
            pb=quote.pb,
            **ttm,
        )

    def _build_profitability(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> Profitability:
        abstract = values["abstract"]
        annual = self._annual_rows(values, request)
        latest_period = next(
            (p for p in fm.all_periods(abstract) if not p.endswith("1231")),
            None,
        )
        latest_quarter = None
        if latest_period is not None:
            rows = fm.build_profitability_periods(
                abstract,
                values.get("balance_sheet") or [],
                values.get("income_statement") or [],
                [latest_period],
            )
            latest_quarter = ProfitabilityPeriod(**rows[0]) if rows else None
        return Profitability(
            annual=[ProfitabilityPeriod(**row) for row in annual],
            latest_quarter=latest_quarter,
        )

    def _build_growth(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> list[GrowthPeriod]:
        return [
            GrowthPeriod(**row) for row in fm.build_growth(self._annual_rows(values, request))
        ]

    def _build_operations_solvency(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> list[OperationsSolvencyPeriod]:
        return [
            OperationsSolvencyPeriod(**row)
            for row in self._operations_rows(values, request)
        ]

    def _build_balance_sheet_flags(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> BalanceSheetFlags:
        abstract = values.get("abstract") or {}
        annual_periods = fm.annual_periods(abstract)
        latest_annual = annual_periods[0] if annual_periods else ""
        flags = fm.build_balance_sheet_flags(
            self._annual_rows(values, request),
            self._operations_rows(values, request),
            values.get("income_statement") or [],
            latest_annual,
        )
        return BalanceSheetFlags(**flags)

    def _build_shareholders(
        self,
        symbol: NormalizedSymbol,
        values: dict[str, Any],
        request: Any,
    ) -> Any:
        return values["shareholders"]

    # ----------------------------------------------------------------- helpers

    def _annual_rows(
        self,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> list[dict[str, Any]]:
        abstract = values.get("abstract") or {}
        periods = fm.annual_periods(abstract)[: request.annual_years]
        if not periods:
            return []
        return fm.build_profitability_periods(
            abstract,
            values.get("balance_sheet") or [],
            values.get("income_statement") or [],
            periods,
        )

    def _operations_rows(
        self,
        values: dict[str, Any],
        request: FundamentalSnapshotRequest,
    ) -> list[dict[str, Any]]:
        abstract = values.get("abstract") or {}
        bs_rows = values.get("balance_sheet") or []
        if not bs_rows:
            return []
        annual, latest = self._report_periods(abstract, bs_rows)
        periods = sorted(set(annual[:3] + latest[:1]), reverse=True)
        return fm.build_operations_solvency(bs_rows, abstract, periods)

    @staticmethod
    def _report_periods(
        abstract: dict[str, Any],
        bs_rows: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        """报告期发现：优先财务摘要列；摘要缺失时回退资产负债表自身的报告日。"""
        if abstract:
            return fm.annual_periods(abstract), fm.all_periods(abstract)
        bs_periods = sorted(
            {str(row.get("报告日")) for row in bs_rows if row.get("报告日")},
            reverse=True,
        )
        annual = [p for p in bs_periods if p.endswith("1231")]
        return annual, bs_periods

    def _provider_name(self, source: str) -> str:
        attr, _, default_name = _SOURCE_SPECS[source]
        provider = getattr(self, attr)
        return provider.name if provider is not None else default_name

    def _market_not_supported(self, symbol: NormalizedSymbol) -> FundamentalSnapshotResponse:
        missing = [
            MissingItem(
                item=block,
                reason=(
                    f"unsupported_market: fundamental snapshot supports A-shares only for now "
                    f"({symbol.display_symbol} is {symbol.market})."
                ),
                hint=_HK_HINT,
            )
            for block in SNAPSHOT_SECTIONS
        ]
        return FundamentalSnapshotResponse(
            status="ok",
            provider="multi",
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=FundamentalSnapshotData(
                symbol=symbol,
                providers={},
                missing=missing,
                notes=[_HK_NOTE],
            ),
        )


def _reason(exc: ProviderError) -> str:
    message = f"{exc.error_type.value}: {exc.message}"
    return message[:200]
