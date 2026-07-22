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


class F10Request(BaseModel):
    symbol: str
    section: Literal[
        "company_profile",
        "latest_notice",
        "shareholders",
        "capital_structure",
        "financial_analysis",
    ] = "company_profile"
    max_chars: int = Field(default=4000, gt=0)


class PageSizeRequest(BaseModel):
    symbol: str
    page_size: int = Field(default=20, gt=0)


class F10Data(BaseModel):
    symbol: NormalizedSymbol
    section: str
    provider_section: str
    text: str
    truncated: bool


class F10Response(BaseToolResponse):
    data: F10Data


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
