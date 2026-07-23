# Provider Capabilities

Provider selection is static for a running process. Change environment variables or `.env`, then restart the server. Unknown provider names fail at startup with `config_error`.

## Defaults

- A-share K-line: `tencent` (web.ifzq.gtimg.cn fqkline).
- Hong Kong K-line: `tencent` (web.ifzq.gtimg.cn fqkline).
- Profile: Tencent quote.
- Financial statements: Sina financial report API.
- Fundamental snapshot profile/composition: `eastmoney` (emweb.securities.eastmoney.com PC_HSF10).
- Fundamental snapshot financials: `akshare` (THS financial abstract + Sina statements).
- Announcements: cninfo.

## Provider Notes

- Tencent kline: default A-share and Hong Kong K-line provider (web.ifzq.gtimg.cn fqkline). Both markets use the same HTTP endpoint with exchange-prefixed codes (`sh600519`, `sz000001`, `hk00700`). Supports `day`, `week`, `month` periods and `none`/`qfq`/`hfq` adjustments; `quarter`/`year` return `unsupported_period`. Response row order is date, open, close, high, low, volume; `amount` is not exposed and stays `null`. 北京证券交易所（`bj*`）代码支持不稳，建议避开。
- Tencent quote: default A-share and Hong Kong profile quote provider. A-share and Hong Kong field indices are mapped separately. Supports batched snapshots (comma-joined codes, up to 40 per request).
- mootdx: optional A-share K-line provider, declarable via `AGENTEUM_FIN_A_KLINE_PROVIDER=mootdx`. Declared in project dependencies since 2026-07-23 (its PyPI metadata pins `httpx<0.26`, resolved via a `tool.uv` override to the project's `httpx>=0.28`). Providers still lazy-import and return `provider_unavailable` if the environment lacks `mootdx`. Note: mootdx talks TCP to 通达信 quote servers and needs a stable route to mainland-China IPs; overseas hosts may time out.
- Eastmoney fundamental: default provider for the snapshot's profile / shareholders / capital-structure / business-composition blocks, via `emweb.securities.eastmoney.com/PC_HSF10/{Section}/PageAjax`（CompanySurvey / ShareholderResearch / CapitalStockStructure / BusinessAnalysis，均为 JSON）。主营构成取最新报告期，MAINOP_TYPE 1/2/3 分别映射按行业/按产品/按地区。港股的股本结构与主要股东走 `datacenter.eastmoney.com/securities/api/data/v1/get`（RPT_HKF10_INFO_EQUITYSTR / RPT_HKF10_EQUITYCHG_HOLDER；INFO_EQUITYSTR 取 SHARES_TYPE_CODE=="001" 的总计行，构成明细不可求和）。
- akshare fundamental: default provider for the snapshot's financial blocks. A 股走 `stock_financial_abstract`（同花顺财务摘要，扣非净利润来源）与 `stock_financial_report_sina`（新浪资产负债表/利润表）；港股走东财港股接口族（`stock_financial_hk_analysis_indicator_em` 主要指标年度/报告期、`stock_financial_hk_report_em` IFRS 三大报表长表、`stock_hk_company_profile_em`/`stock_hk_security_profile_em` 公司与证券资料）。同步 requests 实现，服务端以 `asyncio.to_thread` 包装。TTM/扣非 PE/YoY/DuPont/负债率/有息负债等衍生指标由服务端本地计算，A 股口径与 workspace 技能 company-fundamental-analysis 一致；港股口径见 stock-tools-guide 的 limitations。
- Sina: default A-share financial statements provider, using the `report_date` and `report_list` response shape.
- cninfo: default A-share announcements provider.

## Data Freshness

Each source updates on its own schedule; do not assume consistent freshness across tools, and cross-validate time-sensitive data.

- Tencent quote/profile: real-time trading-day snapshot.
- Tencent kline: real-time trading-day bars from web.ifzq.gtimg.cn fqkline covering A-shares and Hong Kong.
- mootdx K-line (optional): real-time trading-day bars from 通达信 quote servers when configured via environment variable.
- Eastmoney fundamental (snapshot): A-share company profile, shareholders, capital structure, and business composition follow periodic disclosures (quarterly/annual reports); Hong Kong share structure and major holders (datacenter RPT_HKF10_*) follow disclosure updates.
- akshare fundamental (snapshot): THS financial abstract and Sina statements update when the issuer publishes periodic reports; Hong Kong eastmoney indicators/statements follow the same disclosure cadence; quote valuation follows the Tencent quote snapshot.
- Sina financial statements: updated when the issuer publishes periodic reports (quarterly/annual).
- cninfo announcements: near-real-time, as filed with the exchange.
- Iwencai structured data (`iwencai_query`): follows disclosure updates (financials, shareholders, ratings). Iwencai search channels (`iwencai_search`): near-real-time indexing of news, research reports, and announcements.

## v1 Limitations

- Hong Kong financial statements and announcements: unsupported_market in v1.
- Hong Kong fundamental snapshot: supported since P1 (2026-07-24) with documented gaps — no deducted-profit caliber, no structured business composition, no holder count; those items appear in `data.missing` with hints (wind-mcp or annual-report notes as the interim path for segments).
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
