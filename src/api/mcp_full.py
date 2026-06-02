from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.errors import ErrorType, ProviderError, is_recoverable
from src.resources.tool_guides import RESOURCE_URIS, resource_text_by_uri
from src.schemas import (
    ErrorDetail,
    F10Request,
    FallbackRecord,
    FinancialStatementsRequest,
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
) -> FastMCP:
    mcp = FastMCP(
        "Agenteum Fin",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
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

    for uri in RESOURCE_URIS:
        _register_resource(mcp, uri)

    return mcp


def _provider_error_response(exc: ProviderError) -> ToolErrorResponse:
    return ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type=exc.error_type.value,
            message=exc.message,
            provider=exc.provider,
            retryable=is_recoverable(exc.error_type),
        ),
        fallbacks=_fallbacks_from_error(exc),
    )


def _validation_error_response(exc: ValidationError) -> ToolErrorResponse:
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
    )


def _fallbacks_from_error(exc: ProviderError) -> list[FallbackRecord]:
    return [fallback for fallback in exc.fallbacks if isinstance(fallback, FallbackRecord)]


def _register_resource(mcp: FastMCP, uri: str) -> None:
    @mcp.resource(uri)
    def read_resource() -> str:
        return resource_text_by_uri(uri)
