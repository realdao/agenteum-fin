import pytest

from src.api.mcp_full import create_mcp_server
from src.errors import ErrorType, ProviderError
from src.resources.tool_guides import RESOURCE_URIS, load_resource_text, resource_text_by_uri
from src.schemas import FallbackRecord, StockNewsData, StockNewsResponse


def _tool_result_data(result):
    if isinstance(result, dict):
        return result
    content = result[0]
    text = getattr(content, "text", None)
    if text is not None:
        import json

        return json.loads(text)
    return content


def test_resource_markdown_files_load():
    assert "stock_kline" in load_resource_text("stock-tools-guide.md")
    assert "stock_news" in load_resource_text("stock-tools-guide.md")
    assert "Tencent" in load_resource_text("providers-capabilities.md")
    assert "opencli" in load_resource_text("providers-capabilities.md")
    assert "agenteum-fin://tools/stock-tools-guide" in RESOURCE_URIS


def test_iwencai_query_guide_resource_loads():
    text = resource_text_by_uri("agenteum-fin://tools/iwencai-query-guide")

    assert "iwencai_query" in text
    assert "iwencai_search" in text
    assert "同花顺问财" in text
    assert "agenteum-fin://tools/iwencai-query-guide" in RESOURCE_URIS


def test_resource_text_by_uri_loads_known_resource():
    text = resource_text_by_uri("agenteum-fin://providers/capabilities")

    assert "Hong Kong K-line" in text


@pytest.mark.asyncio
async def test_mcp_server_can_be_created_with_fake_services():
    mcp = create_mcp_server(
        kline_service=object(),
        profile_service=object(),
        financial_service=object(),
        f10_service=object(),
        announcement_service=object(),
        research_report_service=object(),
        news_service=object(),
    )

    assert mcp.name == "Agenteum Fin"


@pytest.mark.asyncio
async def test_mcp_tool_validation_errors_return_structured_error():
    mcp = create_mcp_server(kline_service=object())

    result = _tool_result_data(
        await mcp.call_tool("stock_kline", {"symbol": "600519", "period": "minute"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'period'")
    assert "validation error for" not in result["error"]["message"]
    assert result["fallbacks"] == []


@pytest.mark.asyncio
async def test_mcp_page_size_validation_errors_return_structured_error():
    mcp = create_mcp_server(announcement_service=object())

    result = _tool_result_data(
        await mcp.call_tool("stock_announcements", {"symbol": "600519", "page_size": 0})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'page_size'")


@pytest.mark.asyncio
async def test_mcp_provider_errors_include_fallback_history():
    fallback = FallbackRecord(from_provider="primary", to_provider="fallback", reason="timeout")

    class FailingProfileService:
        async def get_profiles(self, symbols):
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="fallback",
                message="fallback failed",
                fallbacks=[fallback],
            )

    mcp = create_mcp_server(profile_service=FailingProfileService())

    result = _tool_result_data(await mcp.call_tool("stock_profile", {"symbols": ["600519"]}))

    assert result["status"] == "error"
    assert result["error"]["type"] == "timeout"
    assert result["fallbacks"] == [{"from": "primary", "to": "fallback", "reason": "timeout"}]


@pytest.mark.asyncio
async def test_mcp_stock_news_tool_returns_service_response():
    class FakeNewsService:
        def __init__(self):
            self.calls = []

        async def get_news(self, symbol, time_range="w"):
            self.calls.append((symbol, time_range))
            return StockNewsResponse(
                data=StockNewsData(
                    google=[{"title": "google"}],
                    twitter=[],
                    xueqiu=[],
                )
            )

    news_service = FakeNewsService()
    mcp = create_mcp_server(news_service=news_service)

    result = _tool_result_data(
        await mcp.call_tool("stock_news", {"symbol": "600519", "time_range": "d"})
    )

    assert news_service.calls == [("600519", "d")]
    assert result == {
        "status": "ok",
        "data": {
            "google": [{"title": "google"}],
            "twitter": [],
            "xueqiu": [],
        },
    }


@pytest.mark.asyncio
async def test_mcp_stock_news_validation_errors_return_structured_error():
    mcp = create_mcp_server(news_service=object())

    result = _tool_result_data(
        await mcp.call_tool("stock_news", {"symbol": "600519", "time_range": "year"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'time_range'")


@pytest.mark.asyncio
async def test_mcp_stock_news_provider_errors_return_structured_error():
    class FailingNewsService:
        async def get_news(self, symbol, time_range="w"):
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider="opencli",
                message="opencli did not return usable results from any stock news source.",
            )

    mcp = create_mcp_server(news_service=FailingNewsService())

    result = _tool_result_data(await mcp.call_tool("stock_news", {"symbol": "600519"}))

    assert result["status"] == "error"
    assert result["error"]["type"] == "provider_unavailable"
    assert result["error"]["provider"] == "opencli"
    assert result["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_mcp_iwencai_query_returns_service_envelope():
    class FakeIwencaiService:
        def __init__(self):
            self.calls = []

        async def query(self, request, *, call_type="normal"):
            self.calls.append((request, call_type))
            return {
                "status": "ok",
                "source": "同花顺问财",
                "query": request.query,
                "domain": request.domain,
                "code_count": 0,
                "returned_count": 0,
                "page": request.page,
                "limit": request.limit,
                "has_more": False,
                "datas": [],
                "chunks_info": {},
                "trace_id": "t" * 64,
            }

    service = FakeIwencaiService()
    mcp = create_mcp_server(iwencai_service=service)

    result = _tool_result_data(
        await mcp.call_tool(
            "iwencai_query",
            {"query": "ROE最高的股票", "domain": "finance", "page": 2, "limit": 20},
        )
    )

    assert result["status"] == "ok"
    assert result["source"] == "同花顺问财"
    request, call_type = service.calls[0]
    assert request.query == "ROE最高的股票"
    assert request.domain == "finance"
    assert request.page == 2
    assert request.limit == 20
    assert call_type == "normal"


@pytest.mark.asyncio
async def test_mcp_iwencai_query_is_retry_maps_to_retry_call_type():
    class FakeIwencaiService:
        def __init__(self):
            self.call_types = []

        async def query(self, request, *, call_type="normal"):
            self.call_types.append(call_type)
            return {"status": "ok", "source": "同花顺问财", "datas": []}

    service = FakeIwencaiService()
    mcp = create_mcp_server(iwencai_service=service)

    await mcp.call_tool(
        "iwencai_query",
        {"query": "q", "domain": "finance", "is_retry": True},
    )
    await mcp.call_tool("iwencai_query", {"query": "q", "domain": "finance"})

    assert service.call_types == ["retry", "normal"]


@pytest.mark.asyncio
async def test_mcp_iwencai_search_is_retry_maps_to_retry_call_type():
    class FakeIwencaiService:
        def __init__(self):
            self.call_types = []

        async def search(self, request, *, call_type="normal"):
            self.call_types.append(call_type)
            return {"status": "ok", "source": "同花顺问财", "data": []}

    service = FakeIwencaiService()
    mcp = create_mcp_server(iwencai_service=service)

    await mcp.call_tool(
        "iwencai_search",
        {"query": "q", "channel": "news", "is_retry": True},
    )

    assert service.call_types == ["retry"]


@pytest.mark.asyncio
async def test_mcp_iwencai_search_returns_service_envelope():
    class FakeIwencaiService:
        async def search(self, request, *, call_type="normal"):
            return {
                "status": "ok",
                "source": "同花顺问财",
                "query": request.query,
                "channel": request.channel,
                "size": request.size,
                "returned_count": 1,
                "data": [{"title": "x"}],
                "trace_id": "t" * 64,
            }

    mcp = create_mcp_server(iwencai_service=FakeIwencaiService())

    result = _tool_result_data(
        await mcp.call_tool(
            "iwencai_search",
            {"query": "人工智能", "channel": "news", "size": 5},
        )
    )

    assert result["status"] == "ok"
    assert result["channel"] == "news"
    assert result["returned_count"] == 1


@pytest.mark.asyncio
async def test_mcp_iwencai_query_validation_error_on_bad_domain():
    mcp = create_mcp_server(iwencai_service=object())

    result = _tool_result_data(
        await mcp.call_tool("iwencai_query", {"query": "q", "domain": "crypto"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'domain'")
    assert result["fallbacks"] == []


@pytest.mark.asyncio
async def test_mcp_iwencai_query_validation_error_on_non_positive_page():
    mcp = create_mcp_server(iwencai_service=object())

    result = _tool_result_data(
        await mcp.call_tool(
            "iwencai_query",
            {"query": "q", "domain": "finance", "page": 0},
        )
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'page'")


@pytest.mark.asyncio
async def test_mcp_iwencai_search_validation_error_on_non_positive_size():
    mcp = create_mcp_server(iwencai_service=object())

    result = _tool_result_data(
        await mcp.call_tool(
            "iwencai_search",
            {"query": "q", "channel": "report", "size": 0},
        )
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'size'")


@pytest.mark.asyncio
async def test_mcp_iwencai_tools_return_provider_unavailable_when_disabled():
    mcp = create_mcp_server(iwencai_service=None)

    query_result = _tool_result_data(
        await mcp.call_tool("iwencai_query", {"query": "q", "domain": "finance"})
    )
    search_result = _tool_result_data(
        await mcp.call_tool("iwencai_search", {"query": "q", "channel": "news"})
    )

    for result in (query_result, search_result):
        assert result["status"] == "error"
        assert result["error"]["type"] == "provider_unavailable"
        assert result["error"]["provider"] == "iwencai"
        assert result["fallbacks"] == []


@pytest.mark.asyncio
async def test_mcp_iwencai_query_config_error_when_api_key_missing():
    import httpx

    from src.providers.iwencai.client import IwencaiClient
    from src.services.iwencai_service import IwencaiService

    async def handler(request):
        raise AssertionError("request should not be sent without an API key")

    service = IwencaiService(
        client=IwencaiClient(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            api_key=None,
        )
    )
    mcp = create_mcp_server(iwencai_service=service)

    result = _tool_result_data(
        await mcp.call_tool("iwencai_query", {"query": "q", "domain": "finance"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "config_error"
    assert result["error"]["provider"] == "iwencai"
    assert result["error"]["retryable"] is False
    assert result["source"] == "同花顺问财"
    assert "iwencai.com/skillhub" in result["error"]["message"]


@pytest.mark.asyncio
async def test_mcp_iwencai_query_provider_errors_return_structured_error():
    class FailingIwencaiService:
        async def query(self, request, *, call_type="normal"):
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="iwencai",
                message="iwencai timed out",
            )

    mcp = create_mcp_server(iwencai_service=FailingIwencaiService())

    result = _tool_result_data(
        await mcp.call_tool("iwencai_query", {"query": "q", "domain": "macro"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "timeout"
    assert result["error"]["retryable"] is True
    assert result["source"] == "同花顺问财"


@pytest.mark.asyncio
async def test_mcp_iwencai_error_responses_all_carry_source():
    class FailingIwencaiService:
        async def query(self, request, *, call_type="normal"):
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="iwencai",
                message="iwencai timed out",
            )

        async def search(self, request, *, call_type="normal"):
            raise ProviderError(
                error_type=ErrorType.NETWORK,
                provider="iwencai",
                message="iwencai network error",
            )

    mcp = create_mcp_server(iwencai_service=FailingIwencaiService())

    provider_error_results = [
        _tool_result_data(
            await mcp.call_tool("iwencai_query", {"query": "q", "domain": "finance"})
        ),
        _tool_result_data(
            await mcp.call_tool("iwencai_search", {"query": "q", "channel": "news"})
        ),
    ]
    for result in provider_error_results:
        assert result["status"] == "error"
        assert result["source"] == "同花顺问财"

    mcp_disabled = create_mcp_server(iwencai_service=None)
    unavailable_results = [
        _tool_result_data(
            await mcp_disabled.call_tool("iwencai_query", {"query": "q", "domain": "finance"})
        ),
        _tool_result_data(
            await mcp_disabled.call_tool("iwencai_search", {"query": "q", "channel": "news"})
        ),
    ]
    for result in unavailable_results:
        assert result["status"] == "error"
        assert result["error"]["type"] == "provider_unavailable"
        assert result["source"] == "同花顺问财"

    mcp_dummy = create_mcp_server(iwencai_service=object())
    validation_results = [
        _tool_result_data(
            await mcp_dummy.call_tool(
                "iwencai_query",
                {"query": "q", "domain": "finance", "page": 0},
            )
        ),
        _tool_result_data(
            await mcp_dummy.call_tool(
                "iwencai_search",
                {"query": "q", "channel": "news", "size": 0},
            )
        ),
    ]
    for result in validation_results:
        assert result["status"] == "error"
        assert result["error"]["type"] == "invalid_request"
        assert result["source"] == "同花顺问财"


@pytest.mark.asyncio
async def test_mcp_iwencai_search_config_error_when_api_key_missing():
    import httpx

    from src.providers.iwencai.client import IwencaiClient
    from src.services.iwencai_service import IwencaiService

    async def handler(request):
        raise AssertionError("request should not be sent without an API key")

    service = IwencaiService(
        client=IwencaiClient(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            api_key=None,
        )
    )
    mcp = create_mcp_server(iwencai_service=service)

    result = _tool_result_data(
        await mcp.call_tool("iwencai_search", {"query": "q", "channel": "announcement"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "config_error"
    assert result["error"]["provider"] == "iwencai"
    assert result["source"] == "同花顺问财"
    assert "iwencai.com/skillhub" in result["error"]["message"]


@pytest.mark.asyncio
async def test_mcp_stock_tool_error_responses_do_not_carry_source():
    class FailingProfileService:
        async def get_profiles(self, symbols):
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="tencent",
                message="tencent timed out",
            )

    mcp = create_mcp_server(profile_service=FailingProfileService())

    result = _tool_result_data(await mcp.call_tool("stock_profile", {"symbols": ["600519"]}))

    assert result["status"] == "error"
    assert "source" not in result


def test_create_mcp_server_disables_dns_rebinding_protection_when_remote():
    mcp = create_mcp_server(allow_remote=True)

    security = mcp.settings.transport_security
    assert security is not None
    assert security.enable_dns_rebinding_protection is False


def test_create_mcp_server_keeps_default_localhost_protection_when_local():
    mcp = create_mcp_server(allow_remote=False)

    # transport_security is None so FastMCP auto-enables localhost-only protection
    security = mcp.settings.transport_security
    assert security is not None
    assert "127.0.0.1:*" in security.allowed_hosts
    assert "localhost:*" in security.allowed_hosts
