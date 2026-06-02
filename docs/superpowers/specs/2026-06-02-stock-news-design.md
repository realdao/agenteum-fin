# Stock News Tool Design

Date: 2026-06-02

## Purpose

Add a `stock_news` MCP tool for searching recent stock-related news and social discussion through the external `opencli` command. The tool focuses on message-surface discovery rather than structured market data. It combines Google News, X/Twitter search, and Xueqiu comments into one stable response shape.

The implementation uses the current repository style: API code registers the MCP tool, schemas define request and response contracts, and a service owns validation, symbol handling, command execution, and response assembly. Per the approved design, this feature does not introduce a separate provider class; `StockNewsService` directly wraps `opencli`.

## Tool Surface

```text
stock_news(symbol: str, time_range: "w" | "d" | "m" = "w")
```

Rules:

- `symbol` accepts A-share, Hong Kong, and US-style ticker inputs.
- `time_range` means:
  - `d`: recent day
  - `w`: recent week
  - `m`: recent month
- The public MCP tool returns dictionaries serialized from Pydantic models, matching the existing API style.

Successful result shape:

```json
{
  "status": "ok",
  "data": {
    "google": [],
    "twitter": [],
    "xueqiu": []
  }
}
```

Each source value contains the JSON value returned by its corresponding `opencli` command. The service does not normalize or filter the source payloads.

## Symbol Handling

A-share and Hong Kong symbols use the existing `normalize_symbol` helper. Supported examples include `600519`, `SH600519`, `600519.SH`, `00700`, `HK00700`, and `00700.HK`.

US symbols are accepted as uppercase alphabetic tickers, such as `AAPL` or `MSFT`. They bypass `normalize_symbol` because the current normalizer only supports A-share and Hong Kong numeric symbols.

Xueqiu command symbols are:

- Shanghai A-share: `SH` plus the six-digit code, for example `SH600519`.
- Shenzhen A-share: `SZ` plus the six-digit code, for example `SZ000001`.
- Beijing A-share: `BJ` plus the six-digit code.
- Hong Kong: the bare five-digit code, for example `00700`.
- US ticker: uppercase ticker, for example `AAPL`.

## Company Name Enrichment

For A-share and Hong Kong symbols, `StockNewsService` attempts to call the existing `profile_service.get_profile(symbol)` and read `response.data.name`.

This enrichment is best effort:

- If profile lookup succeeds and returns a name, Google News queries include both display symbol and company name.
- If profile lookup succeeds and returns a name, Twitter/X queries use the company name only.
- If profile lookup fails or returns no name, the news tool still runs using the display symbol.
- Profile lookup failure is not counted as a `stock_news` source failure.

US tickers skip company-name enrichment and search only by ticker.

## Query Construction

Google News command:

```text
opencli google news [keyword] --lang zh --region CN -f json
```

Keyword rules:

- A-share and Hong Kong with a profile name: `"{display_symbol} {company_name}"`.
- A-share and Hong Kong without a profile name: `"{display_symbol}"`.
- US ticker: `"{ticker}"`.

Twitter/X command:

```text
opencli twitter search [query] --product live --limit 30 -f json
```

Query rules:

- Use the company name when profile lookup returns one; otherwise use the display symbol or ticker.
- Append `, since:YYYY-MM-DD`.
- `d` subtracts 1 day from the current UTC date.
- `w` subtracts 7 days from the current UTC date.
- `m` subtracts 30 days from the current UTC date.

The query uses Raw X operators through the plain query string.

Xueqiu command:

```text
opencli xueqiu comments [symbol] -f json
```

The symbol argument is the Xueqiu symbol described in the Symbol Handling section.

## Command Execution

`StockNewsService` executes the three `opencli` commands with `asyncio.create_subprocess_exec`. Commands run independently so one source failure does not block other sources.

The subprocess environment includes:

```text
NODE_NO_WARNINGS=1
```

This is a temporary per-command environment override to keep Node.js warnings out of stdout and preserve clean JSON output.

Each command succeeds only when:

- The process exits with code `0`.
- stdout is valid JSON.

Non-zero exit, invalid JSON stdout, subprocess startup failure, and timeout are treated as source failures. The failed source value becomes `null`.

## Error Handling

Partial success is acceptable:

- If at least one of `google`, `twitter`, or `xueqiu` succeeds, the tool returns `status: "ok"`.
- Failed sources are represented as `null`.

Total failure returns the repository's existing structured provider-error shape through the MCP API:

```json
{
  "status": "error",
  "error": {
    "type": "provider_unavailable",
    "message": "opencli did not return usable results from any stock news source.",
    "provider": "opencli",
    "retryable": true
  },
  "fallbacks": []
}
```

Input validation errors, including invalid `time_range`, use the existing `ValidationError` to structured `invalid_request` mapping.

## Files And Boundaries

Expected implementation files:

- `src/schemas.py`: add `StockNewsRequest`, `StockNewsData`, and `StockNewsResponse`.
- `src/services/stock_news_service.py`: add the service that handles symbol classification, profile enrichment, query construction, subprocess execution, JSON parsing, and response assembly.
- `src/provider_factory.py`: wire `StockNewsService` into `ServiceBundle`.
- `src/api/mcp_full.py`: register the `stock_news` MCP tool and pass the service into `create_mcp_server`.
- `src/app.py`: pass `services.news_service` when creating the MCP server.
- `src/resources/stock-tools-guide.md` and `src/resources/providers-capabilities.md`: document the new tool and its `opencli` dependency.

Tests should live near existing unit tests:

- `tests/unit/services/test_stock_news_service.py`
- `tests/unit/api/test_mcp_full.py`
- `tests/unit/test_provider_factory.py` if service bundle wiring needs explicit coverage.

## Testing Strategy

Automated tests must not call live `opencli`.

Service tests should inject fake command execution behavior into `StockNewsService` so tests can verify commands and outcomes without subprocesses. The service can expose a constructor dependency for a command runner callable, defaulting to the real subprocess runner.

Required service behaviors:

- A-share symbols are normalized and enriched through `profile_service`.
- Profile lookup failure does not fail the news tool.
- US tickers bypass profile lookup.
- Google, Twitter/X, and Xueqiu commands are constructed with the expected arguments.
- `NODE_NO_WARNINGS=1` is used by the real command runner.
- One failed source produces `None` for that source while preserving `status: "ok"` if another source succeeds.
- Three failed sources raise `ProviderError` with `provider_unavailable` and provider `opencli`.
- Invalid symbols raise the existing invalid-symbol flow.

API tests should verify:

- `create_mcp_server` accepts a fake `news_service`.
- `stock_news` returns the fake service result.
- Invalid `time_range` returns a structured `invalid_request` response.
- Provider errors from `StockNewsService` return the standard structured error shape.

## Acceptance Criteria

- `stock_news` is registered on `/mcp/full`.
- `stock_news(symbol, time_range="w")` supports A-share, Hong Kong, and US ticker inputs.
- A-share and Hong Kong searches use company-name enrichment when profile data is available.
- The three `opencli` subcommands run independently with `NODE_NO_WARNINGS=1`.
- At least one successful source returns `status: "ok"` with failed sources as `null`.
- Three failed sources return a structured `provider_unavailable` error for provider `opencli`.
- Unit tests cover command construction, partial failure, total failure, and MCP API behavior without live external commands.
