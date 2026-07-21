from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field, ValidationError

from src.errors import ErrorType, ProviderError, is_recoverable
from src.resources.tool_guides import RESOURCE_URIS, resource_text_by_uri
from src.schemas import (
    ErrorDetail,
    F10Request,
    FallbackRecord,
    FinancialStatementsRequest,
    IwencaiQueryRequest,
    IwencaiSearchRequest,
    KlineRequest,
    PageSizeRequest,
    StockNewsRequest,
    ToolErrorResponse,
)


def create_mcp_server(
    *,
    kline_service: Any | None = None,
    profile_service: Any | None = None,
    financial_service: Any | None = None,
    f10_service: Any | None = None,
    announcement_service: Any | None = None,
    research_report_service: Any | None = None,
    news_service: Any | None = None,
    iwencai_service: Any | None = None,
    allow_remote: bool = False,
) -> FastMCP:
    # FastMCP auto-enables localhost-only DNS-rebinding protection when host is
    # 127.0.0.1/localhost. That blocks remote clients reaching the service via a
    # domain name or public IP (the SDK rejects their Host header with 421).
    # When the operator explicitly opts into remote access via
    # AGENTEUM_ALLOW_REMOTE=true, disable that protection so external Host
    # headers are accepted. Authentication should be handled separately.
    transport_security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=False)
        if allow_remote
        else None
    )
    mcp = FastMCP(
        "Agenteum Fin",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=transport_security,
    )

    @mcp.tool()
    async def stock_kline(
        symbol: str,
        period: str = "day",
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "none",
        limit: int | None = None,
    ) -> dict:
        """Return daily or higher-period OHLCV K-line bars."""
        try:
            request = KlineRequest(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
                limit=limit,
            )
            response = await kline_service.get_kline(request)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_profile(symbol: str) -> dict:
        """Return lightweight structured stock profile, quote, and valuation fields."""
        try:
            response = await profile_service.get_profile(symbol)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_financial_statements(
        symbol: str,
        statement_type: str = "all",
        periods: int = 8,
    ) -> dict:
        """Return A-share balance sheet, income statement, and cash flow statement data."""
        try:
            request = FinancialStatementsRequest(
                symbol=symbol,
                statement_type=statement_type,
                periods=periods,
            )
            response = await financial_service.get_financial_statements(request)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_f10(
        symbol: str,
        section: str = "company_profile",
        max_chars: int = 4000,
    ) -> dict:
        """Return bounded A-share F10 text sections."""
        try:
            request = F10Request(symbol=symbol, section=section, max_chars=max_chars)
            response = await f10_service.get_f10(
                request.symbol,
                section=request.section,
                max_chars=request.max_chars,
            )
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_announcements(symbol: str, page_size: int = 20) -> dict:
        """Return A-share listed-company announcements."""
        try:
            request = PageSizeRequest(symbol=symbol, page_size=page_size)
            response = await announcement_service.get_announcements(
                request.symbol,
                page_size=request.page_size,
            )
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_research_reports(symbol: str, page_size: int = 20) -> dict:
        """Return A-share sell-side research report metadata."""
        try:
            request = PageSizeRequest(symbol=symbol, page_size=page_size)
            response = await research_report_service.get_reports(
                request.symbol,
                page_size=request.page_size,
            )
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_news(symbol: str, time_range: str = "w") -> dict:
        """Return recent stock news and social discussion from opencli sources."""
        try:
            request = StockNewsRequest(symbol=symbol, time_range=time_range)
            response = await news_service.get_news(
                request.symbol,
                time_range=request.time_range,
            )
            return response.model_dump()
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def iwencai_query(
        query: Annotated[
            str,
            Field(
                description=(
                    "自然语言查询，使用标准金融术语，"
                    "如 'ROE最高的股票'、'2024年中国GDP'、'上证指数涨跌幅'"
                ),
            ),
        ],
        domain: Annotated[
            str,
            Field(
                description=(
                    "查询域（11 选 1）："
                    "finance=财务指标（营收、净利润、ROE、负债率、现金流、估值）；"
                    "market=行情数据（价格、涨跌幅、成交量、主力资金流向、技术指标）；"
                    "macro=宏观经济指标（GDP、CPI、PPI、利率、汇率、社融、PMI）；"
                    "industry=行业估值/财务/盈利/行情/板块排名；"
                    "business=公司经营（主营业务构成、客户、供应商、参控股、重大合同）；"
                    "management=股东股本（股本结构、股东户数、前十大股东、实控人）；"
                    "insresearch=机构观点（研报评级、业绩预测、ESG/信用评级、券商金股）；"
                    "astock=A股选股筛选（如 'ROE>20%连续3年'）；"
                    "hkstock=港股筛选；"
                    "sector=板块筛选；"
                    "index=指数行情（上证指数、沪深300、恒生指数等点位/涨跌幅）"
                ),
            ),
        ],
        page: int = 1,
        limit: int = 10,
        is_retry: Annotated[
            bool,
            Field(
                description=(
                    "放宽条件重试时置 true，服务端会以 X-Claw-Call-Type: retry "
                    "标记该请求；首次查询保持 false"
                ),
            ),
        ] = False,
    ) -> dict:
        """Query THS Iwencai (同花顺问财) structured data by natural language.

        Tool routing rules:
        (a) Known symbol needing K-line, financial statements, F10, announcements,
            research reports, or per-stock news -> use the stock_* tools.
        (b) Stock screening, ranking, cross-section comparison, macro, industry,
            or index queries -> use this tool with the matching domain.
        (c) Keyword search over news / research reports / announcements ->
            use iwencai_search instead.

        Data source is 同花顺问财 (Iwencai); answers built on this data must credit
        同花顺问财. On first use of a domain, or when a query fails or returns
        empty, read resource agenteum-fin://tools/iwencai-query-guide first.
        When retrying with relaxed conditions (at most 2 retries), set
        is_retry=true so the gateway marks the request as a retry.
        """
        if iwencai_service is None:
            return _provider_unavailable_response(
                "iwencai",
                "Iwencai provider is disabled (AGENTEUM_FIN_IWENCAI_PROVIDER=none).",
                source=_IWENCAI_SOURCE,
            ).model_dump(by_alias=True)
        try:
            request = IwencaiQueryRequest(query=query, domain=domain, page=page, limit=limit)
            return await iwencai_service.query(
                request,
                call_type="retry" if is_retry else "normal",
            )
        except ProviderError as exc:
            return _provider_error_response(exc, source=_IWENCAI_SOURCE).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc, source=_IWENCAI_SOURCE).model_dump(by_alias=True)

    @mcp.tool()
    async def iwencai_search(
        query: Annotated[
            str,
            Field(
                description=(
                    "主题关键词搜索，如 '人工智能最新政策'、'人工智能行业研究报告'、"
                    "'贵州茅台分红公告'"
                ),
            ),
        ],
        channel: Annotated[
            str,
            Field(
                description=(
                    "搜索频道（3 选 1）：news=财经资讯（政策动态、行业革新、企业业务进展）；"
                    "report=投研机构研究报告（分析逻辑、投资评级、目标价）；"
                    "announcement=A股/港股/基金/ETF公告（定期报告、分红派息、回购增持、资产重组）"
                ),
            ),
        ],
        size: int = 10,
        is_retry: Annotated[
            bool,
            Field(
                description=(
                    "放宽条件重试时置 true，服务端会以 X-Claw-Call-Type: retry "
                    "标记该请求；首次查询保持 false"
                ),
            ),
        ] = False,
    ) -> dict:
        """Search THS Iwencai (同花顺问财) news, research reports, or announcements.

        Tool routing rules:
        (a) Known symbol needing K-line, financial statements, F10, announcements,
            research reports, or per-stock news -> use the stock_* tools.
        (b) Stock screening, ranking, cross-section comparison, macro, industry,
            or index queries -> use iwencai_query instead.
        (c) Keyword/topic search over news, research reports, or announcements ->
            use this tool with the matching channel.

        Data source is 同花顺问财 (Iwencai); answers built on this data must credit
        同花顺问财. On first use of a channel, or when a search fails or returns
        empty, read resource agenteum-fin://tools/iwencai-query-guide first.
        When retrying with relaxed conditions (at most 2 retries), set
        is_retry=true so the gateway marks the request as a retry.
        """
        if iwencai_service is None:
            return _provider_unavailable_response(
                "iwencai",
                "Iwencai provider is disabled (AGENTEUM_FIN_IWENCAI_PROVIDER=none).",
                source=_IWENCAI_SOURCE,
            ).model_dump(by_alias=True)
        try:
            request = IwencaiSearchRequest(query=query, channel=channel, size=size)
            return await iwencai_service.search(
                request,
                call_type="retry" if is_retry else "normal",
            )
        except ProviderError as exc:
            return _provider_error_response(exc, source=_IWENCAI_SOURCE).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc, source=_IWENCAI_SOURCE).model_dump(by_alias=True)

    for uri in RESOURCE_URIS:
        _register_resource(mcp, uri)

    return mcp


_IWENCAI_SOURCE = "同花顺问财"


def _provider_unavailable_response(
    provider: str,
    message: str,
    *,
    source: str | None = None,
) -> ToolErrorResponse:
    return ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type=ErrorType.PROVIDER_UNAVAILABLE.value,
            message=message,
            provider=provider,
            retryable=is_recoverable(ErrorType.PROVIDER_UNAVAILABLE),
        ),
        fallbacks=[],
        source=source,
    )


def _provider_error_response(
    exc: ProviderError,
    *,
    source: str | None = None,
) -> ToolErrorResponse:
    return ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type=exc.error_type.value,
            message=exc.message,
            provider=exc.provider,
            retryable=is_recoverable(exc.error_type),
        ),
        fallbacks=_fallbacks_from_error(exc),
        source=source,
    )


def _validation_error_response(
    exc: ValidationError,
    *,
    source: str | None = None,
) -> ToolErrorResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first_error.get("loc", []))
    message = first_error.get("msg", "Invalid request")
    if field:
        message = f"Invalid parameter '{field}': {message}"
    return ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type=ErrorType.INVALID_REQUEST.value,
            message=message,
            provider=None,
            retryable=False,
        ),
        fallbacks=[],
        source=source,
    )


def _fallbacks_from_error(exc: ProviderError) -> list[FallbackRecord]:
    return [fallback for fallback in exc.fallbacks if isinstance(fallback, FallbackRecord)]


def _register_resource(mcp: FastMCP, uri: str) -> None:
    @mcp.resource(uri)
    def read_resource() -> str:
        return resource_text_by_uri(uri)
