# Agenteum Fin

Agenteum Fin is an HTTP-only MCP server for conservative stock research data access.

It exposes one MCP endpoint at `/mcp/full` and normalizes selected A-share and Hong Kong stock data domains behind stable tool contracts.

## Run

```powershell
uv run agenteum-fin
```

The server listens on `http://127.0.0.1:8766` by default and exposes MCP at `/mcp/full`.

## Remote Access

Binding a remote host (for example `AGENTEUM_HOST=0.0.0.0`) requires `AGENTEUM_ALLOW_REMOTE=true`. Setting it also disables the MCP SDK's localhost-only DNS-rebinding protection, so remote clients can reach the service via a hostname or public IP (their `Host` header is accepted). v1 has no authentication; do not expose a remote bind address to an untrusted network.

## Test

```powershell
uv run pytest -q
uv run ruff check .
```

Default tests use fixtures and fake providers. Live provider probes live in `playground/provider_probe.py` and `playground/iwencai_probe.py`.

## Iwencai Flexible Query Layer

Two tools proxy the THS Iwencai (同花顺问财) OpenAPI as a flexible query layer behind an `IWENCAI_API_KEY`:

- `iwencai_query(query, domain, page, limit, is_retry)`: natural-language structured data across 11 domains (finance, market, macro, industry, business, management, insresearch, astock, hkstock, sector, index).
- `iwencai_search(query, channel, size, is_retry)`: keyword search over `news`, `report`, and `announcement` channels.

Both envelopes are an independent contract (dynamic fields such as `source`, `query`, `datas`/`data`) and intentionally do not follow the `BaseToolResponse` model of the stock_* tools. Set `is_retry=true` when retrying with relaxed conditions so the gateway marks the request as a retry.

Routing guidance and per-domain examples live in the MCP resource `agenteum-fin://tools/iwencai-query-guide`. Disable the layer with `AGENTEUM_FIN_IWENCAI_PROVIDER=none`.

## Linux Service Deployment

`deploy/linux/` provides a systemd unit and install scripts for Ubuntu hosts:

```bash
uv sync                                  # must exist before installing
sudo deploy/linux/install-service.sh     # renders, enables, and starts the unit
sudo deploy/linux/uninstall-service.sh   # stops and removes the unit
```

The service runs `agenteum-fin` from the project venv as the invoking user (or a system `agenteum` user when installed as root), restarts on failure, and appends logs to `logs/agenteum-fin.{out,err}.log`. Configuration is read from the project `.env`; edit it and run `systemctl restart agenteum-fin`. Remote access additionally requires `AGENTEUM_HOST=0.0.0.0` and `AGENTEUM_ALLOW_REMOTE=true` (see Remote Access).

## Provider Switching

Provider selection is static for a running process. Change `.env`, then restart the server.
