from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def create_mcp_server(**services) -> FastMCP:
    return FastMCP(
        "Agenteum Fin",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
