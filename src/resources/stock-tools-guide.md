# Agenteum Fin Stock Tools

Use these tools for conservative listed-company research. All tools normalize common A-share symbols such as `600519`, `SH600519`, and `600519.SH`; Hong Kong symbols such as `00700`, `hk00700`, and `00700.HK`; and return structured error objects instead of provider exceptions.

## stock_kline

Purpose: daily and higher-period OHLCV bars.

Parameters: `symbol`, `period` (`day`, `week`, `month`, `quarter`, `year`), optional `start_date`, optional `end_date`, `adjust` (`none`, `qfq`, `hfq`), and optional positive `limit`.

Coverage: A-shares use the configured A-share K-line provider, default `mootdx`. Hong Kong K-line returns `unsupported_market` in v1 because no stable provider passed the checkpoint.

Limitations: v1 does not calculate technical indicators. Adjusted K-line modes `qfq` and `hfq` return `unsupported_adjustment` for the default provider.

## stock_profile

Purpose: lightweight company profile, quote, valuation, volume, amount, market-cap, and best-effort metadata fields.

Parameters: `symbol`.

Coverage: A-shares and Hong Kong stocks use Tencent quote by default.

Limitations: industry, listing date, total shares, and float shares may be `null` because the default Tencent quote provider does not reliably expose them. Tencent A-share volume is normalized from lots to shares, and amount is normalized from ten-thousand CNY units. Tencent Hong Kong amount is HKD when usable; PB and turnover rate are `null` unless a stable mapping is verified.

## stock_financial_statements

Purpose: A-share balance sheet, income statement, and cash flow statement data.

Parameters: `symbol`, `statement_type` (`balance_sheet`, `income`, `cash_flow`, `all`), and positive `periods`.

Coverage: A-shares use Sina by default. Hong Kong symbols return `unsupported_market` in v1.

Limitations: v1 preserves provider field codes and Chinese item titles instead of forcing a universal accounting taxonomy.

## stock_f10

Purpose: bounded A-share F10 text sections for research context.

Parameters: `symbol`, `section` (`company_profile`, `latest_notice`, `shareholders`, `capital_structure`, `financial_analysis`), and positive `max_chars`.

Coverage: A-shares use `mootdx` by default. Hong Kong symbols return `unsupported_market`.

Limitations: output is raw provider text trimmed to `max_chars`; use `truncated` to decide whether to ask for a larger slice.

## stock_announcements

Purpose: A-share listed-company announcement metadata.

Parameters: `symbol` and positive `page_size`.

Coverage: A-shares use cninfo by default. Hong Kong symbols return `unsupported_market` in v1.

## stock_research_reports

Purpose: A-share sell-side research report metadata, ratings, and available EPS forecast fields.

Parameters: `symbol` and positive `page_size`.

Coverage: A-shares use Eastmoney reportapi by default. Hong Kong symbols return `unsupported_market` in v1.

## stock_news

Purpose: recent stock news and social discussion from Google News, Twitter/X, and Xueqiu through the external `opencli` command.

Parameters: `symbol` and `time_range` (`w`, `d`, `m`). The default `time_range` is `w`.

Coverage: A-share and Hong Kong symbols use existing symbol normalization and best-effort company-name enrichment from `stock_profile`. US-style alphabetic tickers such as `AAPL` are accepted directly and skip company-name enrichment.

Search details: Google News searches use display symbol plus company name when available. Twitter/X searches use the company name when available, otherwise the display symbol or ticker, and append `, since:YYYY-MM-DD`. Xueqiu Hong Kong comments use the bare five-digit symbol such as `00700`.

Limitations: this tool returns each `opencli` JSON payload as-is. It does not deduplicate, rank, translate, or summarize results. If one source fails, that source is `null`; if all three sources fail, the tool returns `provider_unavailable` for provider `opencli`.

## Fallbacks And Errors

Every successful response includes `provider`, `provider_status`, `fetched_at`, and `fallbacks`. Same-provider retry can be enabled by server configuration for `timeout`, `network`, and `provider_5xx`. Provider fallback is conservative and only applies to recoverable provider errors when multiple providers are configured. Future-version candidates live in `docs/future-requirements.md`.
