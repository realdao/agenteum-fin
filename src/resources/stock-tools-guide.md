# Agenteum Fin Stock Tools

Use these tools for conservative listed-company research. All tools normalize common A-share symbols such as `600519`, `SH600519`, and `600519.SH`; Hong Kong symbols such as `00700`, `hk00700`, and `00700.HK`; and return structured error objects instead of provider exceptions. Per-stock news and sell-side research reports are served by `iwencai_search` (channels `news` and `report`), not by the stock_* tools.

## stock_kline

Purpose: daily and higher-period OHLCV bars.

Parameters: `symbol`, `period` (`day`, `week`, `month`, `quarter`, `year`), optional `start_date`, optional `end_date`, `adjust` (`none`, `qfq`, `hfq`), and optional positive `limit`.

Coverage: A-shares and Hong Kong K-line both use the configured provider, default `tencent` (fqkline, web.ifzq.gtimg.cn), supporting `day`/`week`/`month` periods. `mootdx` remains available as a backup A-share provider via `AGENTEUM_FIN_A_KLINE_PROVIDER=mootdx`, supporting `day`/`week`/`month`/`quarter`/`year`.

Limitations: v1 does not calculate technical indicators. Default `tencent` provider does not support `quarter` and `year` periods (returns `unsupported_period`) and bars expose `volume` but not `amount`. 北交所（`bj*`）codes are not well supported by the default tencent provider. mootdx alternative supports `quarter`/`year` and `amount`, but only `adjust=none`.

## stock_profile

Purpose: quote, valuation, volume, amount, market-cap, and best-effort profile fields for one or more stocks.

Parameters: `symbols` — a list of 1 to 40 symbols; A-share and Hong Kong symbols can be mixed in one call.

Coverage: A-shares and Hong Kong stocks use Tencent quote by default, fetched as a single batched request. Per-symbol failures do not fail the batch: invalid symbols and symbols the provider did not return are listed in `data.errors` (`invalid_symbol` / `symbol_not_found`), while successful entries are in `data.profiles`.

Limitations: industry, listing date, total shares, and float shares may be `null` because the default Tencent quote provider does not reliably expose them. When you need industry classification, listing date, or share counts, query `iwencai_query` with the full company name (domain `management` for share structure, `finance`/`business` for industry context) instead. Tencent A-share volume is normalized from lots to shares, and amount is normalized from ten-thousand CNY units. Tencent Hong Kong amount is HKD when usable; Hong Kong turnover rate is `null` because no stable mapping is verified.

## stock_financial_statements

Purpose: A-share balance sheet, income statement, and cash flow statement data.

Parameters: `symbol`, `statement_type` (`balance_sheet`, `income`, `cash_flow`, `all`), and positive `periods`.

Coverage: A-shares use Sina by default. Hong Kong symbols return `unsupported_market` in v1.

Limitations: v1 preserves provider field codes and Chinese item titles instead of forcing a universal accounting taxonomy. Line items whose value is null upstream (for example insurance- or banking-only accounts on an industrial company) are dropped to keep responses compact.

## stock_fundamental_snapshot

Purpose: one-call structured A-share fundamental snapshot for company analysis, covering seven dimensions: 商业模式/定位 (meta/profile), 业务结构 (business_composition), 估值快照 (quote_valuation), 盈利能力 (profitability), 成长性 (growth), 运营能力 (operations_solvency), 债务风险 (operations_solvency/balance_sheet_flags), plus shareholders.

Parameters: `symbol`, optional `sections` (list of block names, default `["all"]`; one or more of `meta`, `profile`, `business_composition`, `quote_valuation`, `profitability`, `growth`, `operations_solvency`, `balance_sheet_flags`, `shareholders`), and `annual_years` (1-10, default 5) controlling the number of annual periods in `profitability`/`growth`.

Sources: eastmoney F10 (profile/shareholders/capital/business composition, structured JSON), Tencent quote (price/market-cap/PE/PB), akshare (THS financial abstract incl. 扣非净利润, Sina balance sheet & income statement). Derived metrics (TTM, deducted PE, YoY, DuPont, liability ratio, interest-bearing debt, receivable days) are computed server-side. All amounts are in 亿元 CNY; ratios are percentages; `null` means the source did not disclose the field (no fabrication).

Limitations: A-shares only for now — Hong Kong symbols do not error but return all blocks `null` with entries in `data.missing` pointing at wind-mcp as the interim path. Block-level degradation: a failing provider nulls only its dependent blocks and is reported in `data.missing` with the error; `data.providers` lists which providers backed each block; `data.notes` documents 口径 (TTM window, 扣非 preference,期末 ROE/ROA, simplified receivable days). Inherent gaps (customer concentration, volume-price split, market size, peer comparison, industry-chain position) are always listed in `data.missing` with hints. For full 三表 line items use `stock_financial_statements`; for disclosures use `stock_announcements`.

## stock_announcements

Purpose: A-share listed-company announcement metadata.

Parameters: `symbol` and positive `page_size`.

Coverage: A-shares use cninfo by default. Hong Kong symbols return `unsupported_market` in v1.

## Fallbacks And Errors

Every successful response includes `provider`, `provider_status`, `fetched_at`, and `fallbacks`. Same-provider retry can be enabled by server configuration for `timeout`, `network`, and `provider_5xx`. Provider fallback is conservative and only applies to recoverable provider errors when multiple providers are configured. Future-version candidates live in `docs/future-requirements.md`.
