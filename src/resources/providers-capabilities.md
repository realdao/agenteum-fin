# Provider Capabilities

Provider selection is static for a running process. Change environment variables or `.env`, then restart the server. Unknown provider names fail at startup with `config_error`.

## Defaults

- A-share K-line: `mootdx`.
- Hong Kong K-line: `tencent` (web.ifzq.gtimg.cn fqkline).
- Profile: Tencent quote.
- Financial statements: Sina financial report API.
- F10: `mootdx`.
- Announcements: cninfo.
- Research reports: Eastmoney reportapi.

## Provider Notes

- mootdx: default A-share K-line and F10 provider, declared in project dependencies since 2026-07-23 (its PyPI metadata pins `httpx<0.26`, resolved via a `tool.uv` override to the project's `httpx>=0.28`). Providers still lazy-import and return `provider_unavailable` if the environment lacks `mootdx`. Note: mootdx talks TCP to 通达信 quote servers and needs a stable route to mainland-China IPs; overseas hosts may time out.
- Tencent quote: default A-share and Hong Kong profile quote provider. A-share and Hong Kong field indices are mapped separately. Supports batched snapshots (comma-joined codes, up to 40 per request).
- Tencent kline: default Hong Kong K-line provider (web.ifzq.gtimg.cn fqkline). Supports `day`, `week`, `month` periods and `none`/`qfq`/`hfq` adjustments; `quarter`/`year` return `unsupported_period`. Response row order is date, open, close, high, low, volume; `amount` is not exposed and stays `null`.
- Sina: default A-share financial statements provider, using the `report_date` and `report_list` response shape.
- cninfo: default A-share announcements provider.
- Eastmoney reportapi: default A-share research reports provider.

## v1 Limitations

- Hong Kong financial statements, announcements, and research reports: unsupported_market in v1.
- Adjusted K-line modes qfq and hfq: unsupported_adjustment for the default A-share provider (`mootdx`); the default Hong Kong provider (`tencent`) supports them.
- Per-stock news is served by `iwencai_search` (channel `news`); the former opencli-based `stock_news` tool was removed because opencli requires a browser environment unavailable on headless servers.
- Eastmoney push2 and push2his are not defaults because live POC showed proxy instability in this environment.
- Baidu concept blocks, shareholder count, margin trading, hot topics, and institution consensus EPS remain future-version candidates.

## Fallback And Retry

Same-provider retry is controlled by `AGENTEUM_FIN_RETRY_ATTEMPTS` and `AGENTEUM_FIN_RETRY_BACKOFF_SECONDS`. Retries apply only to `timeout`, `network`, and `provider_5xx`.

Provider fallback is a service-layer policy. It is allowed only for recoverable provider errors: `timeout`, `network`, `provider_5xx`, `invalid_response`, and `provider_unavailable`. It is not used for invalid symbols, unsupported markets, unsupported adjustments, auth errors, or configuration errors. Fallback records are returned in the response `fallbacks` field.
