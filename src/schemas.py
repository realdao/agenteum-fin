from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_serializer

from src.utils.dates import parse_optional_date
from src.utils.symbols import NormalizedSymbol


class ProviderStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    FALLBACK = "fallback"


ToolStatus = Literal["ok", "error"]


class FallbackRecord(BaseModel):
    from_provider: str = Field(serialization_alias="from")
    to_provider: str = Field(serialization_alias="to")
    reason: str


class ErrorDetail(BaseModel):
    type: str
    message: str
    provider: str | None = None
    retryable: bool = False


class ToolErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    error: ErrorDetail
    fallbacks: list[FallbackRecord] = Field(default_factory=list)
    # 可选来源标注；iwencai 工具的所有错误响应注入 "同花顺问财"。
    # 为 None 时序列化省略该键，stock_* 工具错误响应保持原样不带 source。
    source: str | None = None

    @model_serializer(mode="wrap")
    def _omit_none_source(self, handler):
        data = handler(self)
        if data.get("source") is None:
            data.pop("source", None)
        return data


class BaseToolResponse(BaseModel):
    status: ToolStatus = "ok"
    provider: str
    provider_status: ProviderStatus = ProviderStatus.OK
    fetched_at: str
    fallbacks: list[FallbackRecord] = Field(default_factory=list)


class KlineRequest(BaseModel):
    symbol: str
    period: Literal["day", "week", "month", "quarter", "year"] = "day"
    start_date: str | None = None
    end_date: str | None = None
    adjust: Literal["none", "qfq", "hfq"] = "none"
    limit: int | None = Field(default=None, gt=0)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        parsed = parse_optional_date(value)
        return parsed.isoformat() if parsed is not None else None


class KlineBar(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None


class KlineData(BaseModel):
    symbol: NormalizedSymbol
    period: str
    adjust: str
    bars: list[KlineBar]


class KlineResponse(BaseToolResponse):
    data: KlineData


class StockProfileData(BaseModel):
    symbol: NormalizedSymbol
    name: str | None = None
    market: str | None = None
    exchange: str | None = None
    price: float | None = None
    last_close: float | None = None
    change_amount: float | None = None
    change_percent: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    turnover_rate: float | None = None
    amount: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    industry: str | None = None
    listing_date: str | None = None
    total_shares: float | None = None
    float_shares: float | None = None
    currency: str | None = None
    metadata_sources: dict[str, str] = Field(default_factory=dict)


class StockProfilesRequest(BaseModel):
    # 上限 40：腾讯快照接口单批次的实测稳妥数量。
    symbols: list[str] = Field(min_length=1, max_length=40)


class StockProfileItemError(BaseModel):
    symbol: str
    error: ErrorDetail


class StockProfilesData(BaseModel):
    profiles: list[StockProfileData]
    errors: list[StockProfileItemError] = Field(default_factory=list)


class StockProfileResponse(BaseToolResponse):
    data: StockProfilesData


class FinancialStatementsRequest(BaseModel):
    symbol: str
    statement_type: Literal["balance_sheet", "income", "cash_flow", "all"] = "all"
    periods: int = Field(default=8, gt=0)


class FinancialLineItem(BaseModel):
    field_code: str
    title: str
    value: Any = None
    display_type: str | None = None
    group_number: str | None = None
    source_statement_type: str
    yoy_value: Any = None


class FinancialStatementPeriod(BaseModel):
    period: str
    description: str | None = None
    publish_date: str | None = None
    currency: str | None = None
    audit_status: str | None = None
    items: list[FinancialLineItem]


class FinancialStatementGroup(BaseModel):
    statement_type: str
    periods: list[FinancialStatementPeriod]


class FinancialStatementsData(BaseModel):
    symbol: NormalizedSymbol
    statements: list[FinancialStatementGroup]


class FinancialStatementsResponse(BaseToolResponse):
    data: FinancialStatementsData


# stock_fundamental_snapshot 的可选 block 名；"all" 表示全部 block。
SNAPSHOT_SECTIONS = (
    "meta",
    "profile",
    "business_composition",
    "quote_valuation",
    "profitability",
    "growth",
    "operations_solvency",
    "balance_sheet_flags",
    "shareholders",
)


class FundamentalSnapshotRequest(BaseModel):
    symbol: str
    sections: list[str] = Field(default_factory=lambda: ["all"])
    annual_years: int = Field(default=5, gt=0, le=10)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sections must not be empty")
        deduped = list(dict.fromkeys(value))
        invalid = [section for section in deduped if section not in (*SNAPSHOT_SECTIONS, "all")]
        if invalid:
            raise ValueError(
                f"invalid sections {invalid}; "
                f"valid values are 'all' or one of {list(SNAPSHOT_SECTIONS)}"
            )
        return deduped


class SnapshotMeta(BaseModel):
    name: str | None = None
    full_name: str | None = None
    market: str | None = None
    exchange: str | None = None
    industry_sw: str | None = None
    industry_csrc: str | None = None
    currency: str | None = None
    listing_date: str | None = None
    total_shares: float | None = None
    float_shares: float | None = None
    limited_shares: float | None = None


class SnapshotProfile(BaseModel):
    introduction: str | None = None
    business_scope: str | None = None
    founded_date: str | None = None
    listing_date: str | None = None
    chairman: str | None = None
    president: str | None = None
    secretary: str | None = None
    legal_person: str | None = None
    employees: float | None = None
    reg_address: str | None = None
    office_address: str | None = None
    website: str | None = None
    controller: str | None = None
    controller_ratio_pct: float | None = None


class BusinessCompositionItem(BaseModel):
    name: str | None = None
    revenue_yi: float | None = None
    cost_yi: float | None = None
    gross_profit_yi: float | None = None
    gross_margin_pct: float | None = None
    revenue_pct: float | None = None


class BusinessComposition(BaseModel):
    period: str | None = None
    by_industry: list[BusinessCompositionItem] = Field(default_factory=list)
    by_product: list[BusinessCompositionItem] = Field(default_factory=list)
    by_region: list[BusinessCompositionItem] = Field(default_factory=list)


class QuoteValuation(BaseModel):
    price: float | None = None
    market_cap_yi: float | None = None
    float_market_cap_yi: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    ttm_revenue_yi: float | None = None
    ttm_net_profit_yi: float | None = None
    ttm_deducted_net_profit_yi: float | None = None
    pe_ttm_calculated: float | None = None
    pe_ttm_deducted: float | None = None
    ps_ttm: float | None = None


class ProfitabilityPeriod(BaseModel):
    period: str
    revenue_yi: float | None = None
    net_profit_yi: float | None = None
    deducted_net_profit_yi: float | None = None
    operating_cash_flow_yi: float | None = None
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    roe_pct: float | None = None
    roa_pct: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    goodwill_yi: float | None = None


class Profitability(BaseModel):
    annual: list[ProfitabilityPeriod] = Field(default_factory=list)
    latest_quarter: ProfitabilityPeriod | None = None


class GrowthPeriod(BaseModel):
    period: str
    revenue_yoy_pct: float | None = None
    net_profit_yoy_pct: float | None = None
    deducted_net_profit_yoy_pct: float | None = None


class OperationsSolvencyPeriod(BaseModel):
    period: str
    cash_yi: float | None = None
    trading_financial_assets_yi: float | None = None
    accounts_receivable_yi: float | None = None
    inventory_yi: float | None = None
    receivable_days_simple: float | None = None
    liability_ratio_pct: float | None = None
    current_ratio: float | None = None
    interest_bearing_debt_yi: float | None = None
    goodwill_yi: float | None = None
    long_term_equity_investment_yi: float | None = None


class BalanceSheetFlags(BaseModel):
    interest_bearing_debt_yi: float | None = None
    trading_financial_assets_yi: float | None = None
    goodwill_yi: float | None = None
    long_term_equity_investment_yi: float | None = None
    investment_income_yi: float | None = None
    fair_value_gain_yi: float | None = None
    fair_value_gain_to_net_profit: float | None = None


class ShareholderItem(BaseModel):
    rank: int | None = None
    name: str | None = None
    holder_type: str | None = None
    shares: float | None = None
    ratio_pct: float | None = None
    change_shares: float | None = None


class Shareholders(BaseModel):
    holder_count: float | None = None
    holder_count_date: str | None = None
    holder_count_change_pct: float | None = None
    controller: str | None = None
    controller_ratio_pct: float | None = None
    top10_date: str | None = None
    top10: list[ShareholderItem] = Field(default_factory=list)
    top10_float: list[ShareholderItem] = Field(default_factory=list)


class MissingItem(BaseModel):
    item: str
    reason: str
    hint: str | None = None


class FundamentalSnapshotData(BaseModel):
    symbol: NormalizedSymbol
    meta: SnapshotMeta | None = None
    profile: SnapshotProfile | None = None
    business_composition: BusinessComposition | None = None
    quote_valuation: QuoteValuation | None = None
    profitability: Profitability | None = None
    growth: list[GrowthPeriod] | None = None
    operations_solvency: list[OperationsSolvencyPeriod] | None = None
    balance_sheet_flags: BalanceSheetFlags | None = None
    shareholders: Shareholders | None = None
    providers: dict[str, list[str]] = Field(default_factory=dict)
    missing: list[MissingItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FundamentalSnapshotResponse(BaseToolResponse):
    data: FundamentalSnapshotData


class PageSizeRequest(BaseModel):
    symbol: str
    page_size: int = Field(default=20, gt=0)


class AnnouncementItem(BaseModel):
    title: str | None = None
    announcement_type: str | None = None
    date: str | None = None
    announcement_id: str | None = None
    url: str | None = None


class AnnouncementsData(BaseModel):
    symbol: NormalizedSymbol
    announcements: list[AnnouncementItem]


class AnnouncementsResponse(BaseToolResponse):
    data: AnnouncementsData


IwencaiDomain = Literal[
    "finance",
    "market",
    "macro",
    "industry",
    "business",
    "management",
    "insresearch",
    "astock",
    "hkstock",
    "sector",
    "index",
]

IwencaiChannel = Literal["news", "report", "announcement"]


class IwencaiQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    domain: IwencaiDomain
    page: int = Field(default=1, gt=0)
    limit: int = Field(default=10, gt=0)


class IwencaiSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    channel: IwencaiChannel
    size: int = Field(default=10, gt=0)
