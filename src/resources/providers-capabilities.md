# Provider Capabilities

Provider selection is static for a running process. Change environment variables or `.env`, then restart the server. Unknown provider names fail at startup with `config_error`.

## Defaults

- A-share K-line: `mootdx`.
- Hong Kong K-line: `none`.
- Profile: Tencent quote.
- Financial statements: Sina financial report API.
- F10: `mootdx`.
- Announcements: cninfo.
- Research reports: Eastmoney reportapi.
- Stock news: external `opencli` command.

## Provider Notes

- mootdx: default A-share K-line and F10 provider, lazy-loaded because current package metadata conflicts with the MCP SDK dependency graph. If `mootdx` is not installed in the runtime environment, K-line and F10 calls return `provider_unavailable`.
- Tencent quote: default A-share and Hong Kong profile quote provider. A-share and Hong Kong field indices are mapped separately.
- Sina: default A-share financial statements provider, using the `report_date` and `report_list` response shape.
- cninfo: default A-share announcements provider.
- Eastmoney reportapi: default A-share research reports provider.
- opencli: external CLI used by `stock_news` for Google News, Twitter/X live search, and Xueqiu comments. Runtime environments must have `opencli` installed and available on `PATH`; commands run with `NODE_NO_WARNINGS=1` to keep stdout parseable as JSON.

## v1 Limitations

- Hong Kong K-line: unsupported_market in v1 because no stable provider passed the checkpoint.
- Hong Kong financial statements, announcements, and research reports: unsupported_market in v1.
- Adjusted K-line modes qfq and hfq: unsupported_adjustment for the default v1 provider.
- `stock_news` depends on `opencli` and returns raw source JSON. Automated tests use fake command runners and do not call live `opencli`.
- Eastmoney push2 and push2his are not defaults because live POC showed proxy instability in this environment.
- Baidu concept blocks, stock news, shareholder count, margin trading, hot topics, and institution consensus EPS remain future-version candidates.

## Fallback And Retry

Same-provider retry is controlled by `AGENTEUM_FIN_RETRY_ATTEMPTS` and `AGENTEUM_FIN_RETRY_BACKOFF_SECONDS`. Retries apply only to `timeout`, `network`, and `provider_5xx`.

Provider fallback is a service-layer policy. It is allowed only for recoverable provider errors: `timeout`, `network`, `provider_5xx`, `invalid_response`, and `provider_unavailable`. It is not used for invalid symbols, unsupported markets, unsupported adjustments, auth errors, or configuration errors. Fallback records are returned in the response `fallbacks` field.
