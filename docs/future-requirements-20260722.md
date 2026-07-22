# Future Requirements Inbox — 2026-07-22 Snapshot

This file supersedes `future-requirements.md` as the current planning view.
The original file is kept untouched for history. Items here are not committed
scope; each needs its own design review, provider validation, and
implementation plan before work starts.

Context for this snapshot: the iwencai flexible query layer
(`iwencai_query` / `iwencai_search`, 11 domains + 3 channels) landed on
2026-07-21, and on 2026-07-22 the Tencent provider was extended to HK K-line
and batched profiles.

## Already Covered — Do Not Rebuild

Covered by iwencai_query domains (validated live on 2026-07-21/22):

- Institution forecast and consensus EPS → `insresearch` domain.
- Shareholder research and shareholder count → `management` domain.
- Industry classification and industry market performance → `industry` domain.
- Business segmentation (主营业务构成) → `business` domain.
- Macro data (GDP/CPI/PPI/利率/汇率/社融/PMI) → `macro` domain.
  The earlier "FRED-first" note for macro is obsolete for China macro.
- Hong Kong stock screening → `hkstock` domain.
- Hot topics / strong-stock screening → `astock` / `sector` domains
  (natural-language screening, not the 同花顺热点 reason-tag feed).
- A-share / Hong Kong / fund / ETF announcement search →
  `iwencai_search` announcement channel.
- Hong Kong single-stock historical daily K-line (OHLCV) → verified live
  2026-07-22: `market`/`hkstock` domains return per-date columns
  (`收盘价[yyyymmdd]` etc.) for ranges up to at least 250 trading days;
  values cross-checked equal to Tencent fqkline. Caveats: phrasing-sensitive
  (must state fields + range explicitly), wide pivoted shape needs reshaping,
  burns API quota, no clear adjustment (复权) control.

Covered by dedicated providers (added 2026-07-22):

- Hong Kong K-line → `stock_kline` via Tencent fqkline (default
  `AGENTEUM_FIN_HK_KLINE_PROVIDER=tencent`; day/week/month, none/qfq/hfq,
  no `amount` field, quarter/year unsupported).
- Batch quote/valuation snapshots → `stock_profile` accepts up to 40
  symbols per call (one batched Tencent request).

## Stock Data — Still Open

- A-share stock news (dedicated provider; the former opencli-based `stock_news`
  tool was removed because opencli needs a browser environment unavailable on
  headless servers — iwencai news channel is the current substitute).
- 同花顺热点 reason tags (人工标注题材归因) — iwencai screening does not
  expose these tags; a dedicated provider is still needed for theme
  attribution.
- Concept blocks (百度 PAE 三维归属).
- Fund flow minute and historical data (百度 PAE / 同花顺北向).
- Dragon-tiger list.
- Lockup expiry.
- Dividend history.
- Block trades.
- Margin trading.
- iwencai usage-cost observability: quota consumption is invisible today;
  consider logging/metering before agents use iwencai domains heavily.

## Hong Kong Stocks — Still Open

- Hong Kong financial statements (iwencai `finance` domain may partially
  cover; needs validation before building a dedicated provider).
- Hong Kong research reports (`iwencai_search` report channel is
  Chinese-research focused; coverage for HK names needs validation).
- Hong Kong profile field completion: turnover rate has no verified Tencent
  field mapping; `pe_static` candidates (idx 57/71) are unverified.

## Other Markets And Domains — Still Open

- US stocks.
- Cryptocurrency K-lines.

## Tooling / Architecture — Still Open

- Unify response envelopes: iwencai tools return a documented raw-dict
  envelope while stock_* tools use `BaseToolResponse`; acceptable but should
  stay a conscious, documented split.
- MCP tool boilerplate: 9 tools repeat the same
  ProviderError/ValidationError handling; extract a shared wrapper when the
  next tool is added.
- Capability matrix doc (market × data-domain) so coverage gaps are visible
  without reading provider code.
- Tencent A-share K-line as mootdx fallback (mootdx requires domestic IP;
  Tencent fqkline works over plain HTTP and already supports A-share codes).
