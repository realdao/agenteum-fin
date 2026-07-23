# Provider Capabilities

Provider selection is static for a running process. Change environment variables or `.env`, then restart the server. Unknown provider names fail at startup with `config_error`.

## Defaults

- A-share K-line: `tencent` (web.ifzq.gtimg.cn fqkline).
- Hong Kong K-line: `tencent` (web.ifzq.gtimg.cn fqkline).
- Profile: Tencent quote.
- Financial statements: Sina financial report API.
- F10: `eastmoney` (emweb.securities.eastmoney.com + datacenter-web).
- Announcements: cninfo.

## Provider Notes

- Tencent kline: default A-share and Hong Kong K-line provider (web.ifzq.gtimg.cn fqkline). Both markets use the same HTTP endpoint with exchange-prefixed codes (`sh600519`, `sz000001`, `hk00700`). Supports `day`, `week`, `month` periods and `none`/`qfq`/`hfq` adjustments; `quarter`/`year` return `unsupported_period`. Response row order is date, open, close, high, low, volume; `amount` is not exposed and stays `null`. 北京证券交易所（`bj*`）代码支持不稳，建议避开。
- Tencent quote: default A-share and Hong Kong profile quote provider. A-share and Hong Kong field indices are mapped separately. Supports batched snapshots (comma-joined codes, up to 40 per request).
- mootdx: optional A-share K-line and F10 provider, declarable via `AGENTEUM_FIN_A_KLINE_PROVIDER=mootdx` / `AGENTEUM_FIN_F10_PROVIDER=mootdx`. Declared in project dependencies since 2026-07-23 (its PyPI metadata pins `httpx<0.26`, resolved via a `tool.uv` override to the project's `httpx>=0.28`). Providers still lazy-import and return `provider_unavailable` if the environment lacks `mootdx`. Note: mootdx talks TCP to 通达信 quote servers and needs a stable route to mainland-China IPs; overseas hosts may time out.
- Eastmoney F10: default A-share F10 provider. `company_profile` / `shareholders` / `capital_structure` 走 `emweb.securities.eastmoney.com/PC_HSF10/{Section}/PageAjax`（JSON）；`financial_analysis` 走 datacenter-web 主要财务指标接口（`RPT_LICO_FN_CPD`，最近8期报告）；`latest_notice` 走东方财富公告摘要接口（np-anotice-stock，最近15条）。返回人类可读的纯文本，由 StockF10Service 截取 `max_chars` 后输出。受 5 个 section 文字密度差异影响，长 section（如 shareholders）可能在默认 `max_chars=4000` 下被截断，调用方可调大 `max_chars`。
- Sina: default A-share financial statements provider, using the `report_date` and `report_list` response shape.
- cninfo: default A-share announcements provider.

## Data Freshness

Each source updates on its own schedule; do not assume consistent freshness across tools, and cross-validate time-sensitive data.

- Tencent quote/profile: real-time trading-day snapshot.
- Tencent kline: real-time trading-day bars from web.ifzq.gtimg.cn fqkline covering A-shares and Hong Kong.
- mootdx K-line/F10 (optional): real-time trading-day bars and F10 text from 通达信 quote servers when configured via environment variable.
- Eastmoney F10: company profile, shareholder, capital-structure text follow periodic disclosures; financial_analysis reflects the latest 8 reporting periods; latest_notice is near-real-time.
- Sina financial statements: updated when the issuer publishes periodic reports (quarterly/annual).
- cninfo announcements: near-real-time, as filed with the exchange.
- Iwencai structured data (`iwencai_query`): follows disclosure updates (financials, shareholders, ratings). Iwencai search channels (`iwencai_search`): near-real-time indexing of news, research reports, and announcements.

## v1 Limitations

- Hong Kong financial statements and announcements: unsupported_market in v1.
- Adjusted K-line modes qfq and hfq: default provider (`tencent`) supports them on both A-share and Hong Kong. mootdx, when configured as the A-share K-line provider, only supports `adjust=none`; qfq/hfq requests to mootdx would fall back as unsupported adjustment.
- Default tencent kline provider reports `unsupported_period` for `quarter` and `year`; mootdx supports those periods when configured.
- Default tencent kline bars expose `volume` but not `amount`; mootdx bars expose both.
- East Money 北交所 (`bj*`) K-line bars are not well supported by the default tencent kline provider.
- Research reports are served by `iwencai_search` (channel `report`); the former Eastmoney-based `stock_research_reports` tool was removed because reportapi coverage lagged iwencai by years on some names.
- Per-stock news is served by `iwencai_search` (channel `news`); the former opencli-based `stock_news` tool was removed because opencli requires a browser environment unavailable on headless servers.
- Eastmoney push2 and push2his are not defaults because live POC showed proxy instability in this environment.
- Baidu concept blocks, shareholder count, margin trading, hot topics, and institution consensus EPS remain future-version candidates.

## Fallback And Retry

Same-provider retry is controlled by `AGENTEUM_FIN_RETRY_ATTEMPTS` and `AGENTEUM_FIN_RETRY_BACKOFF_SECONDS`. Retries apply only to `timeout`, `network`, and `provider_5xx`.

Provider fallback is a service-layer policy. It is allowed only for recoverable provider errors: `timeout`, `network`, `provider_5xx`, `invalid_response`, and `provider_unavailable`. It is not used for invalid symbols, unsupported markets, unsupported adjustments, auth errors, or configuration errors. Fallback records are returned in the response `fallbacks` field.
