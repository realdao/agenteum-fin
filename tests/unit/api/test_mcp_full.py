import pytest

from src.api.mcp_full import create_mcp_server
from src.errors import ErrorType, ProviderError
from src.resources.tool_guides import RESOURCE_URIS, load_resource_text, resource_text_by_uri
from src.schemas import FallbackRecord


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
    assert "Tencent" in load_resource_text("providers-capabilities.md")
    assert "agenteum-fin://tools/stock-tools-guide" in RESOURCE_URIS


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
        async def get_profile(self, symbol):
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="fallback",
                message="fallback failed",
                fallbacks=[fallback],
            )

    mcp = create_mcp_server(profile_service=FailingProfileService())

    result = _tool_result_data(await mcp.call_tool("stock_profile", {"symbol": "600519"}))

    assert result["status"] == "error"
    assert result["error"]["type"] == "timeout"
    assert result["fallbacks"] == [{"from": "primary", "to": "fallback", "reason": "timeout"}]
