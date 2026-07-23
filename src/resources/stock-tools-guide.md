# Agenteum Fin Stock Tools

Use these tools for conservative listed-company research. All tools normalize common A-share symbols such as `600519`, `SH600519`, and `600519.SH`; Hong Kong symbols such as `00700`, `hk00700`, and `00700.HK`; and return structured error objects instead of provider exceptions. Per-stock news and sell-side research reports are served by `iwencai_search` (channels `news` and `report`), not by the stock_* tools.

## stock_kline

Purpose: daily and higher-period OHLCV bars.

Parameters: `symbol`, `period` (`day`, `week`, `month`, `quarter`, `year`), optional `start_date`, optional `end_date`, `adjust` (`none`, `qfq`, `hfq`), and optional positive `limit`.

Coverage: A-shares use the configured A-share K-line provider, default `mootdx`. Hong Kong K-line uses the configured Hong Kong provider, default `tencent` (fqkline), supporting `day`/`week`/`month` periods.

Limitations: v1 does not calculate technical indicators. Adjusted K-line modes `qfq` and `hfq` return `unsupported_adjustment` for the default A-share provider but are supported by the default Hong Kong provider. Tencent Hong Kong bars do not expose `amount`.

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

## stock_f10

Purpose: bounded A-share F10 text sections for research context.

Parameters: `symbol`, `section` (`company_profile`, `latest_notice`, `shareholders`, `capital_structure`, `financial_analysis`), and positive `max_chars`.

Coverage: A-shares use `mootdx` by default. Hong Kong symbols return `unsupported_market`.

Limitations: output is raw provider text trimmed to `max_chars`; use `truncated` to decide whether to ask for a larger slice.

## stock_announcements

Purpose: A-share listed-company announcement metadata.

Parameters: `symbol` and positive `page_size`.

Coverage: A-shares use cninfo by default. Hong Kong symbols return `unsupported_market` in v1.

## Fallbacks And Errors

Every successful response includes `provider`, `provider_status`, `fetched_at`, and `fallbacks`. Same-provider retry can be enabled by server configuration for `timeout`, `network`, and `provider_5xx`. Provider fallback is conservative and only applies to recoverable provider errors when multiple providers are configured. Future-version candidates live in `docs/future-requirements.md`.
