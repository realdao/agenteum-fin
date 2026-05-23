import pytest

from src.api.mcp_full import create_mcp_server
from src.resources.tool_guides import RESOURCE_URIS, load_resource_text, resource_text_by_uri


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
