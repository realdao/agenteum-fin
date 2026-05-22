# Agenteum Fin v1 Design

Date: 2026-05-22

## 1. Purpose

Agenteum Fin is an HTTP-only MCP server for investment research data. Its goal is to give coding agents one stable, unified interface for common structured finance data, while hiding provider-specific protocols, field quirks, and fallback details behind service contracts.

The first version focuses on listed-company research workflows for A-shares and Hong Kong stocks. It should be conservative: implement only the most reliable data domains by default, keep unstable data sources behind provider boundaries, and leave higher-risk signal data to later versions.

The architecture should follow `D:\workspace\agenteum\agenteum-net`: Python 3.11+, `uv`, FastAPI, official MCP Python SDK Streamable HTTP, Pydantic schemas, provider/service/API separation, resources, unit tests, smoke tests, and opencode-based E2E tests.

## 2. v1 Scope

### Goals

- Provide one HTTP MCP endpoint: `/mcp/full`.
- Expose medium-grained data-domain tools:
  - `stock_kline`
  - `stock_profile`
  - `stock_financial_statements`
  - `stock_f10`
  - `stock_announcements`
  - `stock_research_reports`
- Support A-share symbols in common forms such as `600519`, `SH600519`, `600519.SH`, `SZ000001`, and `000001.SZ`.
- Support Hong Kong stock symbols in common forms such as `hk00700`, `00700.HK`, and `00700`.
- Fully support these required A-share workflows:
  - K-line query.
  - Structured company profile.
  - Listed-company financial statements: balance sheet, income statement, and cash flow statement.
- Support basic Hong Kong stock profile through the Tencent quote provider.
- Treat Hong Kong K-line support as a gated v1 target: it is included only if the early provider-verification checkpoint proves a stable provider. If no provider passes, Hong Kong `stock_kline` returns `unsupported_market` in v1 and the requirement is tracked in `docs/future-requirements.md`.
- Return stable unified schemas regardless of provider.
- Allow provider switching by configuration and server restart.
- Apply conservative fallback only for recoverable provider failures.
- Document provider capabilities and limitations through MCP resources.
- Keep real provider probing in `playground/`, separate from default automated tests.
- Include opencode E2E tests because this MCP is intended for coding-agent clients.

### Non-Goals

- No dynamic runtime provider switching from MCP tool inputs in v1.
- No US stock support in v1.
- No cryptocurrency K-line support in v1.
- No macro data support in v1.
- No industry data tools in v1.
- No Hong Kong financial statement support in v1.
- No Hong Kong announcement or research-report support in v1.
- No technical indicators in K-line output.
- No unified accounting taxonomy across all providers in v1.
- No strategy-signal tools in v1, including capital flow, dragon-tiger list, lockup expiry, dividend history, block trades, hot topics, concept blocks, shareholder count changes, or institution consensus EPS.
- No default automated tests that depend on live finance providers.
- No public unauthenticated deployment target. The service is for trusted local and WSL use.

## 3. Tool Surface

v1 uses data-domain tools rather than one large generic `get_stock_data` tool. This keeps each tool easy for an agent to choose, gives every tool a stable return shape, and lets provider fallback differ by data domain.

### `stock_kline`

Purpose: return OHLCV K-line data.

Input:

```text
stock_kline(
  symbol: str,
  period: "day" | "week" | "month" | "quarter" | "year" = "day",
  start_date: str | None = None,
  end_date: str | None = None,
  adjust: "none" | "qfq" | "hfq" = "none",
  limit: int | None = None
)
```

Rules:

- A-share default provider is `mootdx`.
- Hong Kong K-line has no committed default provider until the implementation provider-verification checkpoint passes.
- If the Hong Kong K-line checkpoint fails, v1 keeps the `stock_kline` tool but returns `unsupported_market` for Hong Kong symbols.
- v1 does not calculate or return technical indicators.
- If a provider only supports a subset of adjustment modes, unsupported modes map to `unsupported_adjustment`.
- `adjust="none"` is the only universally required mode in v1. `qfq` and `hfq` may be enabled only for providers whose adjustment behavior is verified in tests or manual provider probes.

Output:

- Normalized symbol metadata.
- `period`, `adjust`, `provider`, `fetched_at`, and `fallbacks`.
- `bars`: ordered list of `{date, open, high, low, close, volume, amount}` where unavailable fields are `null`.

### `stock_profile`

Purpose: return lightweight structured company profile data.

Input:

```text
stock_profile(symbol: str)
```

Output:

- Normalized symbol metadata.
- Required quote fields: name, market, exchange, price, last close, change amount, change percent, high, low, volume, turnover rate, amount, PE, PB, market cap, float market cap, and provider metadata when the selected provider exposes them.
- Best-effort metadata fields: industry, listing date, total shares, and float shares.
- Fields that cannot be found return `null`.
- `volume` is normalized to shares when possible. Tencent A-share raw volume is reported in lots/hands and must be multiplied by 100 before exposing it as shares.
- `amount` is normalized to the local currency base unit when possible. Tencent A-share `amount_wan` must be multiplied by 10,000; Tencent Hong Kong `amount` is already a raw HKD traded-value field but may be empty or zero-like, so return `null` when the provider value is not usable.
- `turnover_rate` is a percentage value, not a decimal fraction. Tencent Hong Kong turnover-rate mapping is not reliable in the current POC and should return `null` unless a stable mapping is verified.
- Best-effort metadata fields must include field-level source/status metadata when they are populated. They may be `null` in v1 because the default Tencent quote provider does not reliably supply industry or listing date, and the Eastmoney enrichment endpoint failed in the current POC environment.
- F10 text is not included in this tool.

### `stock_financial_statements`

Purpose: return listed-company financial statements.

Input:

```text
stock_financial_statements(
  symbol: str,
  statement_type: "balance_sheet" | "income" | "cash_flow" | "all" = "all",
  periods: int = 8
)
```

Rules:

- v1 supports A-shares only.
- Hong Kong symbols return `unsupported_market`.
- Default provider is Sina financial report API.
- The Sina response shape observed in POC uses `report_date` and `report_list`; implementation must support that structure.
- v1 keeps provider item fields and Chinese item titles in the result rather than forcing every account into a universal taxonomy.

Output:

- Normalized symbol metadata.
- `statements`: one or more statement groups.
- Each statement group contains report period, report description, publish date, currency, audit status, and line items.
- Each line item contains provider field code, title, value, display type, group number, source statement type, and year-over-year value if available.

### `stock_f10`

Purpose: return bounded F10 text sections for A-share research.

Input:

```text
stock_f10(
  symbol: str,
  section: "company_profile" | "latest_notice" | "shareholders" | "capital_structure" | "financial_analysis" = "company_profile",
  max_chars: int = 4000
)
```

Rules:

- v1 supports A-shares only.
- Default provider is `mootdx`.
- `section` must be a whitelist value.
- The provider must explicitly map English section names to mootdx F10 Chinese category names:
  - `company_profile` -> `公司概况`
  - `latest_notice` -> `最新提示`
  - `shareholders` -> `股东研究`
  - `capital_structure` -> `股本结构`
  - `financial_analysis` -> `财务分析`
- The service trims long text to `max_chars` and returns truncation metadata.

### `stock_announcements`

Purpose: return listed-company announcements.

Input:

```text
stock_announcements(symbol: str, page_size: int = 20)
```

Rules:

- v1 supports A-shares through cninfo.
- Hong Kong announcements are not included in v1.
- Default provider is cninfo.

Output:

- Title, announcement type, date, announcement ID, URL, provider, fetched time.

### `stock_research_reports`

Purpose: return sell-side research reports and related forecast fields.

Input:

```text
stock_research_reports(symbol: str, page_size: int = 20)
```

Rules:

- v1 supports A-shares through Eastmoney reportapi.
- Hong Kong research reports are not included in v1.
- Default provider is Eastmoney reportapi.
- PDF download is not required in v1, but PDF URL construction should be returned when `infoCode` is available.

Output:

- Title, publish date, institution, rating, industry, EPS forecast fields, `infoCode`, PDF URL, provider, fetched time.

## 4. Symbol Normalization

All tools accept common stock code formats. Internally they use one normalized symbol model:

```text
market: "a_share" | "hk"
exchange: "sh" | "sz" | "bj" | "hk"
symbol: six-digit A-share code or five-digit HK code
display_symbol: canonical user-facing symbol such as "600519.SH" or "00700.HK"
```

Rules:

- `6` and `9` A-share prefixes map to Shanghai.
- `0`, `2`, and `3` A-share prefixes map to Shenzhen.
- `4` and `8` A-share prefixes map to Beijing.
- `hk` prefix or `.HK` suffix maps to Hong Kong.
- After removing known prefixes and suffixes, five-digit numeric symbols are treated as Hong Kong symbols.
- After removing known prefixes and suffixes, six-digit numeric symbols are treated as A-share symbols unless an explicit Hong Kong prefix/suffix was provided.
- Examples: `00001` is `00001.HK`; `000001` is `000001.SZ`; `hk00001` is `00001.HK`; `000001.HK` is invalid because Hong Kong symbols must normalize to five digits.
- Invalid forms raise `invalid_symbol`.

## 5. Provider Strategy

Providers wrap one external source and one capability. They are responsible for:

- Building provider-specific requests.
- Parsing provider-specific response formats.
- Mapping successful responses into unified result models.
- Translating failures into internal `ProviderError` values.

Providers must not own fallback policy. Services own provider selection and fallback.

### Default Providers

```text
A-share K-line: mootdx
Hong Kong K-line: none until provider-verification checkpoint passes
Profile: Tencent quote for market/valuation fields; best-effort enrichment can populate optional metadata only if a stable provider is verified
Financial statements: Sina financial report API
F10: mootdx
Announcements: cninfo
Research reports: Eastmoney reportapi
```

### Provider Verification Checkpoint

Hong Kong K-line provider selection is the only v1 provider-discovery risk. The implementation plan must include an early verification task before committing Hong Kong K-line support. The task must prove the selected provider can return recent Hong Kong OHLCV data for `00700.HK` and maps cleanly to the `stock_kline` schema. If no provider passes, Hong Kong K-line support moves to `docs/future-requirements.md` and the v1 `stock_kline` tool returns `unsupported_market` for Hong Kong symbols.

Candidate providers may include Tencent-derived endpoints, Eastmoney push2his, or another verified HTTP source. A provider is accepted only if a live probe and a fixture-backed provider test both show the required OHLCV fields.

### Provider Capability Matrix

```text
Provider                  Domain                       v1 status
mootdx                    A-share K-line, F10           default
Tencent quote             A/HK quote/profile fields     default for quote fields
Sina financial reports    A-share financial statements  default
cninfo                    A-share announcements         default
Eastmoney reportapi       A-share research reports      default
Eastmoney push2/push2his  K-line/profile enrichment     not default; POC proxy failures
Baidu PAE                 A-share K-line/concepts       not default; concept POC failed
akshare                   broad wrapper library         not used in v1 default providers
```

`akshare` is intentionally not a v1 fallback. The current `a-stock-data` V3.1 direction removes `akshare` in favor of direct HTTP providers plus `mootdx`. If future needs justify it, `akshare` can be added behind a provider interface for a specific data domain.

### Adjustment Capability

```text
Provider          none  qfq  hfq  Notes
mootdx A-share    yes   no   no   v1 must not promise adjusted bars unless verified separately
Baidu K-line      yes   no   no   MA fields are ignored in v1
Eastmoney K-line  yes   yes  yes  fqt-style mapping, not default due POC proxy failures
HK K-line         no    no   no   not committed until provider-verification checkpoint passes
```

The public tool accepts `qfq` and `hfq`, but services must reject unsupported combinations with `unsupported_adjustment` instead of silently returning unadjusted data.

### Tencent Field Mapping

A-share Tencent quote fields validated in POC:

```text
1 name
2 code
3 price
4 last_close
5 open
6 volume_lot
31 change_amount
32 change_percent
33 high
34 low
36 volume_lot
37 amount_wan
38 turnover_percent
39 pe_ttm
43 amplitude_percent
44 market_cap_yi
45 float_market_cap_yi
46 pb
47 limit_up
48 limit_down
52 pe_static
```

Hong Kong Tencent quote fields validated in POC:

```text
1 name
2 code
3 price
4 last_close
5 open
29 volume
30 quote_time
31 change_amount
32 change_percent
33 high
34 low
37 amount
39 pe_ttm
43 amplitude_percent
44 market_cap_yi
45 float_market_cap_yi
75 currency
```

For Tencent A-share quotes, field 36 is the canonical raw volume field for provider mapping, while field 6 duplicates the same lots/hands value in the quote header. The unified `stock_profile.volume` output should convert this to shares. Field 37 is traded amount in ten-thousand CNY units and should be converted before exposing it as unified `amount`.

For Tencent Hong Kong quotes, field 29 is the canonical raw volume field in shares and field 37 is traded amount in HKD. PB was not identified in the POC and must be returned as `null` unless a stable mapping is verified. Hong Kong daily limit-up/limit-down semantics from A-share quotes must not be inferred from the same numeric indices.

### mootdx K-line Caveat

`mootdx` K-line DataFrames can contain `datetime` both as the index name and as a regular column. Provider implementation must avoid a blind `reset_index()` because it can raise a duplicate-column error. The safe normalization is to drop the existing `datetime` column before resetting the index, or otherwise explicitly construct the output rows without creating duplicate `datetime` columns.

### Observed POC Results

The playground probe at `playground/provider_probe.py` produced these useful findings:

- Tencent A-share quote returned price, volume, amount, PE, PB, market cap, float market cap, limit-up, and limit-down fields.
- Tencent Hong Kong quote returned basic price, volume, amount, and valuation fields, but field indices differ from A-shares and should be mapped separately.
- Baidu A-share K-line with MA returned recent and historical rows, but v1 does not use MA data.
- mootdx returned A-share daily bars and F10 company profile text.
- Sina financial reports returned structured three-statement data through `report_date` and `report_list`.
- cninfo announcements returned recent A-share announcement records.
- Eastmoney reportapi returned research reports and forecast fields.
- Eastmoney margin trading and shareholder count endpoints were validated but belong in the future requirements inbox, not v1.
- Eastmoney push2 and push2his had proxy-related failures in the current environment and should not be v1 defaults.
- Baidu concept block returned `ResultCode=10003` in the current environment and should not be v1 default.
- Eastmoney stock news did not return useful stock news in the current environment and should not be v1 default.
- mootdx finance snapshot returned no usable keys in the POC and should not be the financial statements provider.

If a future Baidu provider is added, it must include the non-standard `Accept: application/vnd.finance-web.v1+json` header, compare `ResultCode` through `str(...)` because the upstream type is unstable, and treat compact date formats and semicolon-delimited payloads as provider-specific parsing concerns.

Sina financial statement POC evidence:

```text
sina_income_statement: ok, report_count=102, sample periods=3, first period=20260331, line items=77
sina_balance_sheet: ok, report_count=102, sample periods=3, first period=20260331, line items=141
sina_cash_flow: ok, report_count=98, sample periods=3, first period=20260331, line items=64
```

## 6. Runtime Configuration

Configuration is read from `.env` or environment variables, following the `agenteum-net` pattern.

```env
AGENTEUM_HOST=127.0.0.1
AGENTEUM_PORT=8766
AGENTEUM_ALLOW_REMOTE=false
AGENTEUM_FIN_REQUEST_TIMEOUT=15.0
AGENTEUM_FIN_RETRY_ATTEMPTS=1
AGENTEUM_FIN_RETRY_BACKOFF_SECONDS=0.5
AGENTEUM_FIN_A_KLINE_PROVIDER=mootdx
AGENTEUM_FIN_HK_KLINE_PROVIDER=none
AGENTEUM_FIN_PROFILE_PROVIDER=tencent
AGENTEUM_FIN_FINANCIAL_STATEMENTS_PROVIDER=sina
AGENTEUM_FIN_F10_PROVIDER=mootdx
AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER=cninfo
AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER=eastmoney
```

Provider selection is static for a running server. To switch providers, change configuration and restart the service.

Documented defaults:

```text
AGENTEUM_HOST                         127.0.0.1
AGENTEUM_PORT                         8766
AGENTEUM_ALLOW_REMOTE                 false
AGENTEUM_FIN_REQUEST_TIMEOUT          15.0
AGENTEUM_FIN_RETRY_ATTEMPTS           1
AGENTEUM_FIN_RETRY_BACKOFF_SECONDS    0.5
AGENTEUM_FIN_A_KLINE_PROVIDER         mootdx
AGENTEUM_FIN_HK_KLINE_PROVIDER        none
AGENTEUM_FIN_PROFILE_PROVIDER         tencent
AGENTEUM_FIN_FINANCIAL_STATEMENTS_PROVIDER sina
AGENTEUM_FIN_F10_PROVIDER             mootdx
AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER   cninfo
AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER eastmoney
```

Retry policy:

- Default behavior is one provider attempt and no same-provider retry.
- A same-provider retry may be enabled by setting `AGENTEUM_FIN_RETRY_ATTEMPTS` greater than `1`.
- Retries are allowed only for `timeout`, `network`, and `provider_5xx`.
- Retry backoff is fixed in v1 using `AGENTEUM_FIN_RETRY_BACKOFF_SECONDS`; exponential backoff is out of scope.
- `mootdx` first-call server selection can take longer than normal. The implementation plan should include a manual startup/provider-probe note for this rather than hiding it behind long automatic retries.

Services may still have conservative fallback chains. Fallback is allowed only for recoverable provider errors:

- `timeout`
- `network`
- `provider_5xx`
- `invalid_response`
- `provider_unavailable`

Fallback is not allowed for:

- `invalid_symbol`
- `unsupported_market`
- `unsupported_period`
- `unsupported_adjustment`
- `invalid_request`
- `auth_error`
- `config_error`

Every tool response includes:

- `provider`
- `provider_status`
- `fetched_at`
- `fallbacks`

## 7. Dependencies

The implementation should mirror `agenteum-net` dependency style and pin broad compatible ranges.

Required runtime dependencies:

```text
fastapi>=0.115,<1
httpx>=0.28,<1
mcp>=1.27.1,<2
mootdx>=0.10,<1
pandas>=2.2,<3
pydantic>=2.11,<3
pydantic-settings>=2.9,<3
python-dotenv>=1,<2
uvicorn[standard]>=0.34,<1
```

Development dependencies:

```text
pytest>=8.3,<9
pytest-asyncio>=0.26,<1
ruff>=0.11,<1
```

`akshare` is not a v1 dependency.

First-party HTTP providers should use `httpx` so timeout, retry, logging, and tests can share one client abstraction. `requests` may appear as an indirect dependency of third-party packages or in playground probes, but production provider code should not call it directly in v1.

## 8. Project Layout

Implementation code lives under `src/`. Tests live under `tests/`.

```text
agenteum-fin/
  pyproject.toml
  README.md
  .env.example
  src/
    __init__.py
    app.py
    config.py
    schemas.py
    errors.py
    api/
      __init__.py
      mcp_full.py
      transport.py
    providers/
      __init__.py
      market_data/
      profile/
      financials/
      f10/
      announcements/
      research/
    services/
      __init__.py
      stock_kline_service.py
      stock_profile_service.py
      financial_statement_service.py
      stock_f10_service.py
      announcement_service.py
      research_report_service.py
    resources/
      __init__.py
      tool_guides.py
      stock-tools-guide.md
      providers-capabilities.md
    utils/
      __init__.py
      symbols.py
      dates.py
      http.py
  tests/
    unit/
    smoke/
    e2e/
  playground/
    provider_probe.py
    provider_probe_results.json
```

The exact provider module names can be refined in the implementation plan, but the boundaries are fixed:

- `providers`: external source adapters only.
- `services`: validation, provider selection, fallback, and response assembly.
- `api`: MCP tool and resource registration only.
- `schemas`: Pydantic contracts.
- `errors`: internal error enum, provider exception, safe payload redaction.
- `resources`: agent-facing tool/provider guidance.
- `utils`: symbol normalization, date parsing, HTTP helpers.

## 9. Error Model

The internal error enum should include the `agenteum-net` provider errors plus finance-specific errors.

Common provider errors:

```text
quota_exhausted
rate_limited
auth_error
config_error
invalid_request
invalid_response
timeout
network
provider_5xx
provider_unavailable
provider_error
```

Finance-specific errors:

```text
invalid_symbol
symbol_not_found
unsupported_market
unsupported_period
unsupported_adjustment
market_closed_or_empty
```

Provider exceptions carry:

- error type
- provider name
- message
- optional HTTP status
- optional provider request ID
- optional redacted/truncated payload for logs

Top-level MCP tool behavior:

- User/input errors should return structured tool errors or structured error results with clear `type` and `message`.
- Provider failures should include provider metadata and fallback history.
- Batch-like tools in v1 are limited, but if future tools accept multiple symbols, item-level partial failures should be preferred.

Structured error result shape:

```json
{
  "status": "error",
  "error": {
    "type": "unsupported_market",
    "message": "Hong Kong financial statements are not supported in v1.",
    "provider": null,
    "retryable": false
  },
  "fallbacks": []
}
```

Successful result shape:

```json
{
  "status": "ok",
  "provider": "tencent",
  "provider_status": "ok",
  "fetched_at": "2026-05-22T14:58:50Z",
  "fallbacks": [],
  "data": {}
}
```

Provider fallback record shape:

```json
{
  "from": "provider_a",
  "to": "provider_b",
  "reason": "timeout"
}
```

## 10. Logging And Health

Logging should follow the `agenteum-net` style: standard Python logging with structured `extra` fields where practical.

Provider logs should include:

- `operation`
- `provider`
- `market`
- `symbol`
- `latency_ms`
- `status`
- `error_type` when failed
- `http_status` when available
- `fallback_count`

Logs must not include API keys, authorization headers, cookies, tokens, or full unbounded provider payloads. Provider errors should expose a safe representation that redacts common secret keys and truncates payload text.

Health endpoints:

- `GET /health` returns a lightweight process health response such as `{"status": "ok"}`.
- `/health` must not call live finance providers.
- Provider health checks are out of scope for the default HTTP health endpoint. Manual provider health lives in `playground/provider_probe.py`.

## 11. MCP API And Resources

v1 exposes one endpoint:

```text
/mcp/full
```

The implementation should use the official MCP Python SDK with Streamable HTTP, matching the `agenteum-net` mounting pattern:

```text
FastMCP(..., stateless_http=True, json_response=True, streamable_http_path="/")
FastAPI app mounts the SDK app at /mcp/full
```

Resources:

```text
agenteum-fin://tools/stock-tools-guide
agenteum-fin://providers/capabilities
```

Resource content should explain:

- Tool purpose.
- Parameters.
- Market coverage.
- Provider defaults.
- Fallback behavior.
- Field limitations.
- Future-version items live in `docs/future-requirements.md`.

## 12. Testing Strategy

Default automated tests must not depend on live finance websites.

### Unit Tests

Provider tests:

- Use fake responses, local fixtures, or `httpx.MockTransport`.
- Verify request construction where practical.
- Verify response mapping into unified schemas.
- Verify provider-specific malformed response handling.
- Verify provider error mapping.

Service tests:

- Use fake providers.
- Verify provider selection by market and config.
- Verify fallback only happens for recoverable error types.
- Verify non-recoverable errors stop fallback.
- Verify `unsupported_market` for Hong Kong financial statements.
- Verify symbol normalization is applied before provider calls.

Schema and utility tests:

- Validate accepted and rejected symbol formats.
- Validate date parsing.
- Validate period and adjustment enums.
- Validate response serialization.

API tests:

- Verify MCP server can be created with fake services.
- Verify tools are registered.
- Verify resources load.

### Smoke Tests

Smoke tests should verify:

- `create_app()` succeeds.
- `/mcp/full` is mounted.
- The server can be started with test settings.

### E2E Tests With opencode

E2E tests are required because the MCP is built for coding-agent clients.

They should follow the shape of `agenteum-net/tests/e2e/test_opencode_mcp.py`:

- Start the Agenteum Fin server on a local port.
- Run `opencode --pure mcp list`.
- Assert `agenteum-fin` appears and is connected.
- Run `opencode --pure run --format json --dangerously-skip-permissions <prompt>`.
- Parse newline-delimited JSON events.
- Assert a `tool_use` event appears for at least one Agenteum Fin tool such as `stock_profile` or `stock_kline`.
- Assert the model passed the expected `symbol` argument into the tool.

The default E2E should prove coding-agent discovery and tool invocation. It should not require successful live finance-provider data unless explicitly marked as an external/manual test.

### Manual Provider Probes

`playground/provider_probe.py` remains the live-source validation tool. It can be expanded as providers are added, but it is not part of the default test suite.

Manual probes should be run before claiming live provider support for a new data domain.

## 13. Future Requirements

Future-version ideas are tracked outside this v1 design in `docs/future-requirements.md`. This keeps the v1 spec focused on committed scope and explicit v1 fallback behavior.

## 14. Acceptance Criteria

v1 is acceptable when:

- The project structure follows the `agenteum-net` architecture style.
- `/mcp/full` is available through MCP Streamable HTTP.
- The six v1 tools are registered and documented.
- A-share `stock_kline`, `stock_profile`, and `stock_financial_statements` work through unified schemas.
- Hong Kong `stock_profile` works through the Tencent quote mapping.
- Hong Kong `stock_kline` either works through a verified provider or returns `unsupported_market` with the capability documented.
- Hong Kong financial statements return `unsupported_market`.
- `stock_f10`, `stock_announcements`, and `stock_research_reports` are implemented with conservative provider behavior.
- Provider switching is configuration-based and restart-based.
- Fallback behavior is tested at the service layer.
- Unit tests and smoke tests pass without live provider access.
- opencode E2E proves a coding agent can discover and invoke the MCP tools.
- `playground/provider_probe.py` documents live provider behavior for implemented providers.
