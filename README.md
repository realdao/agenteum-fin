# Agenteum Fin

Agenteum Fin is an HTTP-only MCP server for conservative stock research data access.

It exposes one MCP endpoint at `/mcp/full` and normalizes selected A-share and Hong Kong stock data domains behind stable tool contracts.

## Run

```powershell
uv run agenteum-fin
```

The server listens on `http://127.0.0.1:8766` by default and exposes MCP at `/mcp/full`.

## Test

```powershell
uv run pytest -q
uv run ruff check .
```

Default tests use fixtures and fake providers. Live provider probes live in `playground/provider_probe.py`.

## Provider Switching

Provider selection is static for a running process. Change `.env`, then restart the server.
