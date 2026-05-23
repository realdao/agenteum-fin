# Provider Capabilities

- mootdx: default A-share K-line and F10 provider, lazy-loaded because current package metadata conflicts with the MCP SDK dependency graph.
- Tencent quote: default A-share and Hong Kong profile quote provider.
- Sina: default A-share financial statements provider.
- cninfo: default A-share announcements provider.
- Eastmoney reportapi: default A-share research reports provider.
- Hong Kong K-line: unsupported_market in v1 because no stable provider passed the checkpoint.
- Hong Kong financial statements, announcements, and research reports: unsupported_market in v1.
- Adjusted K-line modes qfq and hfq: unsupported_adjustment for the default v1 provider.
