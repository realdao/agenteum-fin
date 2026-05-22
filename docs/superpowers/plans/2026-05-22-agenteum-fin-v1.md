# Agenteum Fin v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Agenteum Fin v1 HTTP-only MCP server for conservative stock research data access.

**Architecture:** Mirror `D:\workspace\agenteum\agenteum-net`: FastAPI owns process and health, FastMCP exposes `/mcp/full`, services own validation/provider selection/fallback, providers own one external data source each, and Pydantic schemas define the unified contracts. Live finance providers are not used by default tests; providers are tested with fixtures, fake clients, or `httpx.MockTransport`.

**Tech Stack:** Python 3.11+, uv, FastAPI, official MCP Python SDK, Pydantic v2, pydantic-settings, httpx, mootdx, pandas, pytest, pytest-asyncio, ruff, opencode E2E.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-05-22-agenteum-fin-design.md`
- Future inbox: `docs/future-requirements.md`
- Live provider POC: `playground/provider_probe.py`
- Latest POC result: `playground/provider_probe_results.json`
- Reference architecture: `D:\workspace\agenteum\agenteum-net`
- Reference E2E: `D:\workspace\agenteum\agenteum-net\tests\e2e\test_opencode_mcp.py`

## Execution Notes

- The current workspace is not a git repository. Each task still includes a commit step because this plan may be executed from a git-enabled workspace later. In the current workspace, `git rev-parse --is-inside-work-tree` is expected to fail; when that happens, skip the commit command and list changed files in the task handoff.
- Do not make live provider access part of default unit, smoke, or E2E tests.
- First-party HTTP provider code must use `httpx`, not `requests`.
- Use `playground/provider_probe.py` only for manual provider validation.
- Keep Hong Kong K-line as `unsupported_market` in v1 unless a stable provider passes both a live probe and a fixture-backed provider test before the K-line service is implemented.
- Do not edit the user's `~/.config/opencode/opencode.jsonc` during E2E. The E2E should start Agenteum Fin and use a prompt that triggers opencode to call the already configured MCP interface.
- If Claude non-interactive review needs follow-up rounds, continue the same Claude Code session with `claude --continue -p ...` so review context stays continuous.

## File Structure

Create and modify these files:

```text
agenteum-fin/
  pyproject.toml
  README.md
  .env.example
  src/
    __init__.py
    app.py
    config.py
    errors.py
    schemas.py
    api/
      __init__.py
      mcp_full.py
      transport.py
    providers/
      __init__.py
      announcements/
        __init__.py
        cninfo.py
      f10/
        __init__.py
        mootdx_f10.py
      financials/
        __init__.py
        sina.py
      market_data/
        __init__.py
        mootdx_kline.py
      profile/
        __init__.py
        tencent.py
      research/
        __init__.py
        eastmoney.py
    resources/
      __init__.py
      providers-capabilities.md
      stock-tools-guide.md
      tool_guides.py
    services/
      __init__.py
      announcement_service.py
      financial_statement_service.py
      research_report_service.py
      stock_f10_service.py
      stock_kline_service.py
      stock_profile_service.py
    utils/
      __init__.py
      dates.py
      http.py
      symbols.py
  tests/
    e2e/
      test_opencode_mcp.py
    fixtures/
      cninfo_announcements.json
      eastmoney_research_reports.json
      sina_financial_report.json
      tencent_quote.txt
    smoke/
      test_mcp_http.py
      test_project_imports.py
    unit/
      api/
        test_mcp_full.py
      providers/
        test_cninfo_announcements.py
        test_eastmoney_research.py
        test_mootdx_f10.py
        test_mootdx_kline.py
        test_sina_financials.py
        test_tencent_profile.py
      services/
        test_announcement_service.py
        test_financial_statement_service.py
        test_research_report_service.py
        test_stock_f10_service.py
        test_stock_kline_service.py
        test_stock_profile_service.py
      utils/
        test_dates.py
        test_http.py
        test_symbols.py
      test_config.py
      test_errors.py
      test_schemas.py
```

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: package `__init__.py` files under `src/api`, `src/providers`, `src/providers/*`, `src/resources`, `src/services`, `src/utils`
- Create: `tests/smoke/test_project_imports.py`

- [ ] **Step 1: Write the failing smoke import test**

Create `tests/smoke/test_project_imports.py`:

```python
def test_src_package_imports():
    import src

    assert src.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke import test and verify it fails**

Run:

```powershell
uv run pytest tests/smoke/test_project_imports.py -q
```

Expected: failure because `pyproject.toml` and `src` package do not exist yet.

- [ ] **Step 3: Create project metadata and package files**

Create `pyproject.toml` with:

```toml
[project]
name = "agenteum-fin"
version = "0.1.0"
description = "HTTP-only MCP server for investment research data providers."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1",
  "httpx>=0.28,<1",
  "mcp>=1.27.1,<2",
  "mootdx>=0.10,<1",
  "pandas>=2.2,<3",
  "pydantic>=2.11,<3",
  "pydantic-settings>=2.9,<3",
  "python-dotenv>=1,<2",
  "uvicorn[standard]>=0.34,<1",
]

[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project.scripts]
agenteum-fin = "src.app:main"

[dependency-groups]
dev = [
  "pytest>=8.3,<9",
  "pytest-asyncio>=0.26,<1",
  "ruff>=0.11,<1",
]

[tool.setuptools.packages.find]
include = ["src*"]

[tool.setuptools.package-data]
"src.resources" = ["*.md"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Create `src/__init__.py`:

```python
__version__ = "0.1.0"
```

Create empty `__init__.py` files in every package directory listed in the file structure.

Create `.env.example`:

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

Create `README.md`:

```markdown
# Agenteum Fin

Agenteum Fin is an HTTP-only MCP server for conservative stock research data access.

It exposes one MCP endpoint at `/mcp/full` and normalizes selected A-share and Hong Kong stock data domains behind stable tool contracts.
```

- [ ] **Step 4: Run the smoke import test and verify it passes**

Run:

```powershell
uv run pytest tests/smoke/test_project_imports.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit because this directory is not a git repository.

When running inside a git repository:

```powershell
git add pyproject.toml README.md .env.example src tests/smoke/test_project_imports.py
git commit -m "chore: scaffold agenteum fin project"
```

## Task 2: Core Errors, Symbol Utilities, Dates, And Schemas

**Files:**
- Create: `src/errors.py`
- Create: `src/utils/symbols.py`
- Create: `src/utils/dates.py`
- Create: `src/schemas.py`
- Create: `tests/unit/test_errors.py`
- Create: `tests/unit/utils/test_symbols.py`
- Create: `tests/unit/utils/test_dates.py`
- Create: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing tests for error redaction**

Create `tests/unit/test_errors.py`:

```python
from src.errors import ErrorType, ProviderError, redact_payload


def test_provider_error_safe_repr_redacts_secrets_and_truncates_payload():
    error = ProviderError(
        error_type=ErrorType.AUTH_ERROR,
        provider="sina",
        message="bad key",
        http_status=401,
        payload={
            "api_key": "secret-key",
            "nested": {"authorization": "Bearer secret-token"},
            "body": "x" * 600,
        },
    )

    safe = error.safe_repr()

    assert safe["error_type"] == "auth_error"
    assert safe["provider"] == "sina"
    assert safe["payload"]["api_key"] == "[REDACTED]"
    assert safe["payload"]["nested"]["authorization"] == "[REDACTED]"
    assert safe["payload"]["body"].endswith("[TRUNCATED]")
    assert len(safe["payload"]["body"]) < 530


def test_error_type_contains_finance_specific_values():
    assert ErrorType.UNSUPPORTED_MARKET.value == "unsupported_market"
    assert ErrorType.UNSUPPORTED_ADJUSTMENT.value == "unsupported_adjustment"
    assert ErrorType.INVALID_SYMBOL.value == "invalid_symbol"


def test_redact_payload_handles_lists():
    payload = [{"token": "secret"}, {"value": "visible"}]

    assert redact_payload(payload)[0]["token"] == "[REDACTED]"
    assert redact_payload(payload)[1]["value"] == "visible"
```

- [ ] **Step 2: Write failing tests for symbol normalization**

Create `tests/unit/utils/test_symbols.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.utils.symbols import normalize_symbol


def test_normalizes_shanghai_a_share_variants():
    assert normalize_symbol("600519").model_dump() == {
        "market": "a_share",
        "exchange": "sh",
        "symbol": "600519",
        "display_symbol": "600519.SH",
    }
    assert normalize_symbol("SH600519").display_symbol == "600519.SH"
    assert normalize_symbol("600519.SH").display_symbol == "600519.SH"


def test_normalizes_shenzhen_and_beijing_a_share():
    assert normalize_symbol("000001").display_symbol == "000001.SZ"
    assert normalize_symbol("300750").display_symbol == "300750.SZ"
    assert normalize_symbol("830799").display_symbol == "830799.BJ"


def test_normalizes_hong_kong_variants():
    assert normalize_symbol("00700").model_dump() == {
        "market": "hk",
        "exchange": "hk",
        "symbol": "00700",
        "display_symbol": "00700.HK",
    }
    assert normalize_symbol("hk00700").display_symbol == "00700.HK"
    assert normalize_symbol("00700.HK").display_symbol == "00700.HK"


def test_rejects_explicit_hk_with_six_digit_symbol():
    with pytest.raises(ProviderError) as raised:
        normalize_symbol("000001.HK")

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
```

- [ ] **Step 3: Write failing tests for date parsing**

Create `tests/unit/utils/test_dates.py`:

```python
import pytest

from src.utils.dates import parse_optional_date


def test_parse_optional_date_accepts_iso_date():
    assert parse_optional_date("2026-05-22").isoformat() == "2026-05-22"


def test_parse_optional_date_returns_none_for_none():
    assert parse_optional_date(None) is None


def test_parse_optional_date_rejects_compact_dates_in_public_schema():
    with pytest.raises(ValueError):
        parse_optional_date("20260522")
```

- [ ] **Step 4: Write failing schema serialization tests**

Create `tests/unit/test_schemas.py`:

```python
from src.schemas import (
    ErrorDetail,
    FallbackRecord,
    KlineBar,
    KlineRequest,
    KlineResponse,
    NormalizedSymbol,
    ProviderStatus,
    StockProfileData,
    ToolErrorResponse,
)


def symbol():
    return NormalizedSymbol(
        market="a_share",
        exchange="sh",
        symbol="600519",
        display_symbol="600519.SH",
    )


def test_kline_request_defaults():
    request = KlineRequest(symbol="600519")

    assert request.period == "day"
    assert request.adjust == "none"
    assert request.limit is None


def test_kline_response_serializes_unified_shape():
    response = KlineResponse(
        status="ok",
        provider="mootdx",
        provider_status=ProviderStatus.OK,
        fetched_at="2026-05-22T14:58:50Z",
        fallbacks=[],
        data={
            "symbol": symbol(),
            "period": "day",
            "adjust": "none",
            "bars": [KlineBar(date="2026-05-22", open=1, high=2, low=1, close=2)],
        },
    )

    dumped = response.model_dump()

    assert dumped["status"] == "ok"
    assert dumped["data"]["bars"][0]["date"] == "2026-05-22"


def test_profile_data_allows_null_best_effort_fields():
    data = StockProfileData(
        symbol=symbol(),
        name="贵州茅台",
        price=1290.2,
        industry=None,
        listing_date=None,
        total_shares=None,
        float_shares=None,
    )

    assert data.industry is None


def test_error_response_shape():
    response = ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type="unsupported_market",
            message="Hong Kong financial statements are not supported in v1.",
            provider=None,
            retryable=False,
        ),
        fallbacks=[FallbackRecord(from_provider="a", to_provider="b", reason="timeout")],
    )

    dumped = response.model_dump()

    assert dumped["error"]["type"] == "unsupported_market"
    assert dumped["fallbacks"][0]["from_provider"] == "a"
```

- [ ] **Step 5: Run the tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/test_errors.py tests/unit/utils/test_symbols.py tests/unit/utils/test_dates.py tests/unit/test_schemas.py -q
```

Expected: import errors because `src.errors`, `src.utils.symbols`, `src.utils.dates`, and `src.schemas` are not implemented.

- [ ] **Step 6: Implement the core modules**

Create `src/errors.py` with:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorType(StrEnum):
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    CONFIG_ERROR = "config_error"
    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    TIMEOUT = "timeout"
    NETWORK = "network"
    PROVIDER_5XX = "provider_5xx"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    INVALID_SYMBOL = "invalid_symbol"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    UNSUPPORTED_MARKET = "unsupported_market"
    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_ADJUSTMENT = "unsupported_adjustment"
    MARKET_CLOSED_OR_EMPTY = "market_closed_or_empty"


SECRET_KEYS = ("api_key", "authorization", "cookie", "token", "secret", "password")
MAX_PAYLOAD_TEXT = 500


RECOVERABLE_ERRORS = {
    ErrorType.TIMEOUT,
    ErrorType.NETWORK,
    ErrorType.PROVIDER_5XX,
    ErrorType.INVALID_RESPONSE,
    ErrorType.PROVIDER_UNAVAILABLE,
}


def is_recoverable(error_type: ErrorType) -> bool:
    return error_type in RECOVERABLE_ERRORS


def _is_secret_key(key: str) -> bool:
    key_lower = key.lower()
    return any(secret in key_lower for secret in SECRET_KEYS)


def _truncate(value: str) -> str:
    if len(value) <= MAX_PAYLOAD_TEXT:
        return value
    return f"{value[:MAX_PAYLOAD_TEXT]}[TRUNCATED]"


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: "[REDACTED]" if _is_secret_key(str(key)) else redact_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_payload(item) for item in payload)
    if isinstance(payload, str):
        return _truncate(payload)
    return payload


class ProviderError(Exception):
    def __init__(
        self,
        *,
        error_type: ErrorType,
        provider: str | None,
        message: str,
        http_status: int | None = None,
        request_id: str | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.message = message
        self.http_status = http_status
        self.request_id = request_id
        self.payload = payload

    def safe_repr(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "provider": self.provider,
            "message": self.message,
            "http_status": self.http_status,
            "request_id": self.request_id,
            "payload": redact_payload(self.payload),
        }
```

Create `src/utils/symbols.py` with:

```python
from __future__ import annotations

import re

from pydantic import BaseModel

from src.errors import ErrorType, ProviderError


class NormalizedSymbol(BaseModel):
    market: str
    exchange: str
    symbol: str
    display_symbol: str


def normalize_symbol(raw: str) -> NormalizedSymbol:
    value = raw.strip().upper()
    explicit_hk = value.startswith("HK") or value.endswith(".HK")
    value = re.sub(r"^(SH|SZ|BJ|HK)", "", value)
    suffix = None
    if "." in value:
        value, suffix = value.split(".", 1)
    if not value.isdigit():
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Invalid stock symbol: {raw}",
        )
    if explicit_hk or suffix == "HK" or len(value) == 5:
        if len(value) != 5:
            raise ProviderError(
                error_type=ErrorType.INVALID_SYMBOL,
                provider=None,
                message="Hong Kong symbols must normalize to five digits.",
            )
        return NormalizedSymbol(
            market="hk",
            exchange="hk",
            symbol=value,
            display_symbol=f"{value}.HK",
        )
    if len(value) != 6:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message="A-share symbols must normalize to six digits.",
        )
    exchange = _a_share_exchange(value)
    if suffix is not None and suffix.lower() != exchange:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Symbol suffix {suffix} does not match inferred exchange {exchange}.",
        )
    return NormalizedSymbol(
        market="a_share",
        exchange=exchange,
        symbol=value,
        display_symbol=f"{value}.{exchange.upper()}",
    )


def _a_share_exchange(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return "sh"
    if symbol.startswith(("0", "2", "3")):
        return "sz"
    if symbol.startswith(("4", "8")):
        return "bj"
    raise ProviderError(
        error_type=ErrorType.INVALID_SYMBOL,
        provider=None,
        message=f"Unsupported A-share prefix: {symbol[0]}",
    )
```

Create `src/utils/dates.py` with:

```python
from __future__ import annotations

from datetime import date


def parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)
```

Create `src/schemas.py` with the Pydantic models used by the tests and later services:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.utils.symbols import NormalizedSymbol


class ProviderStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    FALLBACK = "fallback"


ToolStatus = Literal["ok", "error"]


class FallbackRecord(BaseModel):
    from_provider: str = Field(serialization_alias="from")
    to_provider: str = Field(serialization_alias="to")
    reason: str


class ErrorDetail(BaseModel):
    type: str
    message: str
    provider: str | None = None
    retryable: bool = False


class ToolErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    error: ErrorDetail
    fallbacks: list[FallbackRecord] = Field(default_factory=list)


class BaseToolResponse(BaseModel):
    status: ToolStatus = "ok"
    provider: str
    provider_status: ProviderStatus = "ok"
    fetched_at: str
    fallbacks: list[FallbackRecord] = Field(default_factory=list)


class KlineRequest(BaseModel):
    symbol: str
    period: Literal["day", "week", "month", "quarter", "year"] = "day"
    start_date: str | None = None
    end_date: str | None = None
    adjust: Literal["none", "qfq", "hfq"] = "none"
    limit: int | None = None


class KlineBar(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None


class KlineData(BaseModel):
    symbol: NormalizedSymbol
    period: str
    adjust: str
    bars: list[KlineBar]


class KlineResponse(BaseToolResponse):
    data: KlineData | dict[str, Any]


class StockProfileData(BaseModel):
    symbol: NormalizedSymbol
    name: str | None = None
    market: str | None = None
    exchange: str | None = None
    price: float | None = None
    last_close: float | None = None
    change_amount: float | None = None
    change_percent: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    turnover_rate: float | None = None
    amount: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    industry: str | None = None
    listing_date: str | None = None
    total_shares: float | None = None
    float_shares: float | None = None
    currency: str | None = None
    metadata_sources: dict[str, str] = Field(default_factory=dict)


class StockProfileResponse(BaseToolResponse):
    data: StockProfileData


class FinancialStatementsRequest(BaseModel):
    symbol: str
    statement_type: Literal["balance_sheet", "income", "cash_flow", "all"] = "all"
    periods: int = 8


class FinancialLineItem(BaseModel):
    field_code: str
    title: str
    value: Any = None
    display_type: str | None = None
    group_number: str | None = None
    source_statement_type: str
    yoy_value: Any = None


class FinancialStatementPeriod(BaseModel):
    period: str
    description: str | None = None
    publish_date: str | None = None
    currency: str | None = None
    audit_status: str | None = None
    items: list[FinancialLineItem]


class FinancialStatementGroup(BaseModel):
    statement_type: str
    periods: list[FinancialStatementPeriod]


class FinancialStatementsData(BaseModel):
    symbol: NormalizedSymbol
    statements: list[FinancialStatementGroup]


class FinancialStatementsResponse(BaseToolResponse):
    data: FinancialStatementsData


class F10Request(BaseModel):
    symbol: str
    section: Literal[
        "company_profile",
        "latest_notice",
        "shareholders",
        "capital_structure",
        "financial_analysis",
    ] = "company_profile"
    max_chars: int = 4000


class F10Data(BaseModel):
    symbol: NormalizedSymbol
    section: str
    provider_section: str
    text: str
    truncated: bool


class F10Response(BaseToolResponse):
    data: F10Data


class AnnouncementItem(BaseModel):
    title: str | None = None
    announcement_type: str | None = None
    date: str | None = None
    announcement_id: str | None = None
    url: str | None = None


class AnnouncementsData(BaseModel):
    symbol: NormalizedSymbol
    announcements: list[AnnouncementItem]


class AnnouncementsResponse(BaseToolResponse):
    data: AnnouncementsData


class ResearchReportItem(BaseModel):
    title: str | None = None
    publish_date: str | None = None
    institution: str | None = None
    rating: str | None = None
    industry: str | None = None
    eps_forecast: dict[str, Any] = Field(default_factory=dict)
    info_code: str | None = None
    pdf_url: str | None = None


class ResearchReportsData(BaseModel):
    symbol: NormalizedSymbol
    reports: list[ResearchReportItem]


class ResearchReportsResponse(BaseToolResponse):
    data: ResearchReportsData
```

- [ ] **Step 7: Run the tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/test_errors.py tests/unit/utils/test_symbols.py tests/unit/utils/test_dates.py tests/unit/test_schemas.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/errors.py src/utils/symbols.py src/utils/dates.py src/schemas.py tests/unit
git commit -m "feat: add core finance contracts"
```

## Task 3: Configuration, HTTP Helpers, App Shell, And Health

**Files:**
- Create: `src/config.py`
- Create: `src/utils/http.py`
- Create: `src/api/transport.py`
- Create: `src/app.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/unit/utils/test_http.py`
- Create: `tests/smoke/test_mcp_http.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/unit/test_config.py`:

```python
import logging

import pytest

from src.config import Settings, is_remote_bind_host


def test_settings_defaults_match_spec():
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8766
    assert settings.allow_remote is False
    assert settings.fin_request_timeout == 15.0
    assert settings.fin_retry_attempts == 1
    assert settings.fin_a_kline_provider == "mootdx"
    assert settings.fin_hk_kline_provider == "none"


def test_remote_bind_requires_explicit_allow_remote():
    settings = Settings(AGENTEUM_HOST="0.0.0.0", AGENTEUM_ALLOW_REMOTE=False)

    with pytest.raises(ValueError):
        settings.validate_network_binding(logging.getLogger("test"))


def test_loopback_hosts_are_not_remote():
    assert is_remote_bind_host("127.0.0.1") is False
    assert is_remote_bind_host("localhost") is False
    assert is_remote_bind_host("0.0.0.0") is True
```

- [ ] **Step 2: Write failing HTTP helper tests**

Create `tests/unit/utils/test_http.py`:

```python
import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.utils.http import get_json


@pytest.mark.asyncio
async def test_get_json_maps_5xx_to_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad gateway"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError) as raised:
        await get_json(client, "https://example.test/data", provider="example")

    assert raised.value.error_type == ErrorType.PROVIDER_5XX


@pytest.mark.asyncio
async def test_get_json_maps_invalid_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError) as raised:
        await get_json(client, "https://example.test/data", provider="example")

    assert raised.value.error_type == ErrorType.INVALID_RESPONSE
```

- [ ] **Step 3: Write failing app smoke test**

Create `tests/smoke/test_mcp_http.py`:

```python
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings


def test_create_app_mounts_mcp_endpoint():
    app = create_app(Settings())

    paths = {route.path for route in app.routes}

    assert "/mcp/full" in paths or any(path.startswith("/mcp/full") for path in paths)


def test_health_endpoint_is_lightweight():
    app = create_app(Settings())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/test_config.py tests/unit/utils/test_http.py tests/smoke/test_mcp_http.py -q
```

Expected: import errors because config, HTTP helpers, app, and MCP transport are not implemented.

- [ ] **Step 5: Implement config, HTTP helpers, transport, and app shell**

Create `src/config.py` following `agenteum-net`:

```python
from __future__ import annotations

import logging
from functools import cache
from ipaddress import ip_address

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="127.0.0.1", alias="AGENTEUM_HOST")
    port: int = Field(default=8766, alias="AGENTEUM_PORT")
    allow_remote: bool = Field(default=False, alias="AGENTEUM_ALLOW_REMOTE")
    fin_request_timeout: float = Field(default=15.0, alias="AGENTEUM_FIN_REQUEST_TIMEOUT")
    fin_retry_attempts: int = Field(default=1, alias="AGENTEUM_FIN_RETRY_ATTEMPTS")
    fin_retry_backoff_seconds: float = Field(
        default=0.5,
        alias="AGENTEUM_FIN_RETRY_BACKOFF_SECONDS",
    )
    fin_a_kline_provider: str = Field(default="mootdx", alias="AGENTEUM_FIN_A_KLINE_PROVIDER")
    fin_hk_kline_provider: str = Field(default="none", alias="AGENTEUM_FIN_HK_KLINE_PROVIDER")
    fin_profile_provider: str = Field(default="tencent", alias="AGENTEUM_FIN_PROFILE_PROVIDER")
    fin_financial_statements_provider: str = Field(
        default="sina",
        alias="AGENTEUM_FIN_FINANCIAL_STATEMENTS_PROVIDER",
    )
    fin_f10_provider: str = Field(default="mootdx", alias="AGENTEUM_FIN_F10_PROVIDER")
    fin_announcements_provider: str = Field(
        default="cninfo",
        alias="AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER",
    )
    fin_research_reports_provider: str = Field(
        default="eastmoney",
        alias="AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER",
    )

    def validate_network_binding(self, logger: logging.Logger) -> None:
        if not is_remote_bind_host(self.host):
            return
        if not self.allow_remote:
            raise ValueError(
                "Remote bind hosts require AGENTEUM_ALLOW_REMOTE=true "
                "because v1 has no authentication."
            )
        logger.warning(
            "Agenteum Fin is listening on a remote bind host with no authentication.",
            extra={"host": self.host, "port": self.port, "security": "no_authentication"},
        )


def is_remote_bind_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return False
    if normalized in {"0.0.0.0", "::", ""}:
        return True
    try:
        return not ip_address(normalized).is_loopback
    except ValueError:
        return True


@cache
def get_settings() -> Settings:
    return Settings()
```

Create `src/utils/http.py`:

```python
from __future__ import annotations

from typing import Any

import httpx

from src.errors import ErrorType, ProviderError


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        raise ProviderError(
            error_type=ErrorType.TIMEOUT,
            provider=provider,
            message=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            error_type=ErrorType.NETWORK,
            provider=provider,
            message=str(exc),
        ) from exc
    return _json_response(response, provider=provider)


async def post_form_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    data: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.post(url, data=data, headers=headers)
    except httpx.TimeoutException as exc:
        raise ProviderError(
            error_type=ErrorType.TIMEOUT,
            provider=provider,
            message=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            error_type=ErrorType.NETWORK,
            provider=provider,
            message=str(exc),
        ) from exc
    return _json_response(response, provider=provider)


def _json_response(response: httpx.Response, *, provider: str) -> dict[str, Any]:
    if response.status_code >= 500:
        raise ProviderError(
            error_type=ErrorType.PROVIDER_5XX,
            provider=provider,
            message=f"Provider returned HTTP {response.status_code}",
            http_status=response.status_code,
            payload=response.text,
        )
    if response.status_code >= 400:
        raise ProviderError(
            error_type=ErrorType.INVALID_REQUEST,
            provider=provider,
            message=f"Provider returned HTTP {response.status_code}",
            http_status=response.status_code,
            payload=response.text,
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError(
            error_type=ErrorType.INVALID_RESPONSE,
            provider=provider,
            message="Provider returned invalid JSON.",
            http_status=response.status_code,
            payload=response.text,
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderError(
            error_type=ErrorType.INVALID_RESPONSE,
            provider=provider,
            message="Provider JSON response is not an object.",
            http_status=response.status_code,
            payload=payload,
        )
    return payload
```

Create `src/api/transport.py`:

```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette


def mount_mcp_streamable_http(mcp: FastMCP) -> Starlette:
    return mcp.streamable_http_app()
```

Create `src/app.py` with a minimal MCP shell. Later tasks will wire concrete services into this same `create_app` function:

```python
from __future__ import annotations

import contextlib
import logging

import httpx
import uvicorn
from fastapi import FastAPI

from src.api.mcp_full import create_mcp_server
from src.api.transport import mount_mcp_streamable_http
from src.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = logging.getLogger("agenteum_fin")
    settings.validate_network_binding(logger)

    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    mcp = create_mcp_server()
    mcp_app = mount_mcp_streamable_http(mcp)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            try:
                yield
            finally:
                await http_client.aclose()

    app = FastAPI(title="Agenteum Fin", lifespan=lifespan)
    app.mount("/mcp/full", mcp_app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)
```

Create the initial `src/api/mcp_full.py` so app creation works before the MCP tool task adds tools:

```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def create_mcp_server(**services) -> FastMCP:
    return FastMCP(
        "Agenteum Fin",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/test_config.py tests/unit/utils/test_http.py tests/smoke/test_mcp_http.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/config.py src/utils/http.py src/api src/app.py tests/unit/test_config.py tests/unit/utils/test_http.py tests/smoke/test_mcp_http.py
git commit -m "feat: add app shell and runtime settings"
```

## Task 4: Hong Kong K-line Provider Checkpoint

**Files:**
- Modify: `playground/provider_probe.py`
- Modify: `docs/future-requirements.md`
- Create: `tests/unit/services/test_stock_kline_service.py`
- Create: `src/services/stock_kline_service.py`

- [ ] **Step 1: Write the failing service test for Hong Kong K-line unsupported behavior**

Create `tests/unit/services/test_stock_kline_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import KlineRequest
from src.services.stock_kline_service import StockKlineService


@pytest.mark.asyncio
async def test_hk_kline_returns_unsupported_market_when_provider_is_none():
    service = StockKlineService(a_share_provider=None, hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
uv run pytest tests/unit/services/test_stock_kline_service.py::test_hk_kline_returns_unsupported_market_when_provider_is_none -q
```

Expected: import error because `StockKlineService` does not exist.

- [ ] **Step 3: Run the live checkpoint probe manually**

Run:

```powershell
uv run python playground/provider_probe.py
```

Expected based on the latest recorded POC:

```text
eastmoney_daily_kline_hk: error
tencent_quote_hk: ok
```

Decision for this implementation plan: Tencent quote is not a historical K-line source, and Eastmoney HK K-line failed in the current environment, so keep `AGENTEUM_FIN_HK_KLINE_PROVIDER=none` and implement Hong Kong K-line as `unsupported_market` for v1.

- [ ] **Step 4: Implement the minimal service behavior**

Create `src/services/stock_kline_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import KlineRequest, KlineResponse
from src.utils.symbols import normalize_symbol


class StockKlineService:
    def __init__(self, *, a_share_provider: Any, hk_provider: Any = None) -> None:
        self.a_share_provider = a_share_provider
        self.hk_provider = hk_provider

    async def get_kline(self, request: KlineRequest) -> KlineResponse:
        symbol = normalize_symbol(request.symbol)
        if symbol.market == "hk" and self.hk_provider is None:
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Hong Kong K-line data is not supported in v1.",
            )
        if symbol.market == "a_share" and self.a_share_provider is None:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=None,
                message="A-share K-line provider is not configured.",
            )
        provider = self.a_share_provider if symbol.market == "a_share" else self.hk_provider
        data = await provider.get_kline(symbol, request)
        return KlineResponse(
            status="ok",
            provider=provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=data,
        )
```

- [ ] **Step 5: Keep future inbox explicit**

Ensure `docs/future-requirements.md` contains:

```markdown
- Hong Kong K-lines if the v1 provider-verification checkpoint does not find a stable provider.
```

- [ ] **Step 6: Run the test and verify it passes**

Run:

```powershell
uv run pytest tests/unit/services/test_stock_kline_service.py::test_hk_kline_returns_unsupported_market_when_provider_is_none -q
```

Expected: test passes.

- [ ] **Step 7: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add playground/provider_probe.py docs/future-requirements.md src/services/stock_kline_service.py tests/unit/services/test_stock_kline_service.py
git commit -m "feat: lock hong kong kline v1 behavior"
```

## Task 5: Tencent Profile Provider And Stock Profile Service

**Files:**
- Create: `src/providers/profile/tencent.py`
- Create: `src/services/stock_profile_service.py`
- Create: `tests/fixtures/tencent_quote.txt`
- Create: `tests/unit/providers/test_tencent_profile.py`
- Create: `tests/unit/services/test_stock_profile_service.py`

- [ ] **Step 1: Add the Tencent quote fixture**

Create `tests/fixtures/tencent_quote.txt`:

```text
v_sh600519="1~贵州茅台~600519~1290.20~1311.00~1310.95~49157~19572~29585~1290.20~100~1290.19~2~1290.18~16~1290.17~5~1290.16~52~1290.21~9~1290.22~1~1290.24~4~1290.25~12~1290.29~3~~20260522161417~-20.80~-1.59~1311.91~1290.12~1290.20/49157/6372389482~49157~637239~0.39~19.53~~1311.91~1290.12~1.66~16156.79~16156.79~5.96~1442.10~1179.90~1.04~146~1296.33~14.83~19.63~~~0.41~637238.9482~0.0000~0~";
v_hk00700="100~腾讯控股~00700~441.400~439.000~442.200~23998219.0~0~0~441.400~0~0~0~0~0~0~0~0~0~441.400~0~0~0~0~0~0~0~0~0~23998219.0~2026/05/22 16:08:22~2.400~0.55~445.000~438.800~441.400~23998219.0~10609807754.648~0~16.17~~0~0~1.41~40246.9430~40246.9430~TENCENT~1.20~677.700~438.400~0.81~18.60~0~0~0~0~0~15.11~3.16~0.26~100~-25.65~-3.29~GP~20.59~11.53~-5.30~-9.90~-17.14~9118020607.00~9118020607.00~15.29~5.300~442.108~-26.94~HKD~1~50";
```

- [ ] **Step 2: Write failing provider tests**

Create `tests/unit/providers/test_tencent_profile.py`:

```python
import httpx
import pytest

from src.providers.profile.tencent import TencentProfileProvider
from src.utils.symbols import normalize_symbol


def fixture_text() -> str:
    return open("tests/fixtures/tencent_quote.txt", encoding="utf-8").read()


@pytest.mark.asyncio
async def test_tencent_maps_a_share_units():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "q=sh600519" in str(request.url)
        return httpx.Response(200, content=fixture_text().encode("gbk"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TencentProfileProvider(client=client)

    data = await provider.get_profile(normalize_symbol("600519"))

    assert data.name == "贵州茅台"
    assert data.volume == 4_915_700
    assert data.amount == 6_372_390_000
    assert data.turnover_rate == 0.39
    assert data.pe_ttm == 19.53
    assert data.pb == 5.96


@pytest.mark.asyncio
async def test_tencent_maps_hk_fields_without_pb_or_turnover_rate():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "q=hk00700" in str(request.url)
        return httpx.Response(200, content=fixture_text().encode("gbk"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TencentProfileProvider(client=client)

    data = await provider.get_profile(normalize_symbol("00700"))

    assert data.name == "腾讯控股"
    assert data.volume == 23998219.0
    assert data.amount == 10609807754.648
    assert data.turnover_rate is None
    assert data.pb is None
    assert data.currency == "HKD"
```

- [ ] **Step 3: Write failing service tests**

Create `tests/unit/services/test_stock_profile_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import FallbackRecord, StockProfileData
from src.services.stock_profile_service import StockProfileService
from src.utils.symbols import normalize_symbol


class FakeProfileProvider:
    def __init__(self, name="tencent", *, error_type=None):
        self.name = name
        self.error_type = error_type
        self.calls = 0

    async def get_profile(self, symbol):
        self.calls += 1
        if self.error_type:
            raise ProviderError(
                error_type=self.error_type,
                provider=self.name,
                message=f"{self.name} failed",
            )
        return StockProfileData(symbol=symbol, name="贵州茅台", price=1290.2)


@pytest.mark.asyncio
async def test_profile_service_normalizes_symbol_before_provider_call():
    service = StockProfileService(providers=[FakeProfileProvider()])

    response = await service.get_profile("SH600519")

    assert response.status == "ok"
    assert response.provider == "tencent"
    assert response.data.symbol == normalize_symbol("600519")


@pytest.mark.asyncio
async def test_profile_service_falls_back_for_recoverable_errors_only():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.TIMEOUT)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    response = await service.get_profile("600519")

    assert response.provider == "fallback"
    assert response.fallbacks == [
        FallbackRecord(from_provider="primary", to_provider="fallback", reason="timeout")
    ]


@pytest.mark.asyncio
async def test_profile_service_stops_on_non_recoverable_errors():
    first = FakeProfileProvider(name="primary", error_type=ErrorType.AUTH_ERROR)
    second = FakeProfileProvider(name="fallback")
    service = StockProfileService(providers=[first, second])

    with pytest.raises(ProviderError) as raised:
        await service.get_profile("600519")

    assert raised.value.error_type == ErrorType.AUTH_ERROR
    assert second.calls == 0
```

- [ ] **Step 4: Run provider and service tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/providers/test_tencent_profile.py tests/unit/services/test_stock_profile_service.py -q
```

Expected: import errors because provider and service do not exist.

- [ ] **Step 5: Implement Tencent provider and stock profile service**

Create `src/providers/profile/tencent.py`:

```python
from __future__ import annotations

import re

import httpx

from src.errors import ErrorType, ProviderError
from src.schemas import StockProfileData
from src.utils.symbols import NormalizedSymbol


class TencentProfileProvider:
    name = "tencent"
    url = "https://qt.gtimg.cn/q={query}"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_profile(self, symbol: NormalizedSymbol) -> StockProfileData:
        query = self._query_symbol(symbol)
        try:
            response = await self.client.get(
                self.url.format(query=query),
                headers={"User-Agent": "Mozilla/5.0"},
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider=self.name,
                message=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                error_type=ErrorType.NETWORK,
                provider=self.name,
                message=str(exc),
            ) from exc
        text = response.content.decode("gbk", errors="replace")
        values = self._values_for_query(text, query)
        if symbol.market == "hk":
            return self._map_hk(symbol, values)
        return self._map_a_share(symbol, values)

    def _query_symbol(self, symbol: NormalizedSymbol) -> str:
        if symbol.market == "hk":
            return f"hk{symbol.symbol}"
        return f"{symbol.exchange}{symbol.symbol}"

    def _values_for_query(self, text: str, query: str) -> list[str]:
        pattern = rf"v_{re.escape(query)}=\"([^\"]*)\""
        match = re.search(pattern, text)
        if match is None:
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message=f"Tencent quote did not contain {query}.",
                payload=text,
            )
        values = match.group(1).split("~")
        if len(values) < 53:
            raise ProviderError(
                error_type=ErrorType.INVALID_RESPONSE,
                provider=self.name,
                message=f"Tencent quote returned too few fields: {len(values)}.",
                payload=values,
            )
        return values

    def _map_a_share(self, symbol: NormalizedSymbol, values: list[str]) -> StockProfileData:
        return StockProfileData(
            symbol=symbol,
            name=_str(values, 1),
            market=symbol.market,
            exchange=symbol.exchange,
            price=_float(values, 3),
            last_close=_float(values, 4),
            change_amount=_float(values, 31),
            change_percent=_float(values, 32),
            high=_float(values, 33),
            low=_float(values, 34),
            volume=_scale(_float(values, 36), 100),
            amount=_scale(_float(values, 37), 10000),
            turnover_rate=_float(values, 38),
            pe_ttm=_float(values, 39),
            pe_static=_float(values, 52),
            pb=_float(values, 46),
            market_cap=_scale(_float(values, 44), 100000000),
            float_market_cap=_scale(_float(values, 45), 100000000),
            currency="CNY",
        )

    def _map_hk(self, symbol: NormalizedSymbol, values: list[str]) -> StockProfileData:
        return StockProfileData(
            symbol=symbol,
            name=_str(values, 1),
            market=symbol.market,
            exchange=symbol.exchange,
            price=_float(values, 3),
            last_close=_float(values, 4),
            change_amount=_float(values, 31),
            change_percent=_float(values, 32),
            high=_float(values, 33),
            low=_float(values, 34),
            volume=_float(values, 29),
            amount=_null_if_zero(_float(values, 37)),
            turnover_rate=None,
            pe_ttm=_float(values, 39),
            pb=None,
            market_cap=_scale(_float(values, 44), 100000000),
            float_market_cap=_scale(_float(values, 45), 100000000),
            currency=_str(values, 75),
        )


def _str(values: list[str], index: int) -> str | None:
    if index >= len(values):
        return None
    value = values[index].strip()
    return value or None


def _float(values: list[str], index: int) -> float | None:
    value = _str(values, index)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _scale(value: float | None, factor: float) -> float | None:
    if value is None:
        return None
    return value * factor


def _null_if_zero(value: float | None) -> float | None:
    if value in (None, 0):
        return None
    return value
```

Create `src/services/stock_profile_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ProviderError, is_recoverable
from src.schemas import FallbackRecord, StockProfileResponse
from src.utils.symbols import normalize_symbol


class StockProfileService:
    def __init__(self, *, providers: list[Any]) -> None:
        self.providers = providers

    async def get_profile(self, symbol: str) -> StockProfileResponse:
        normalized = normalize_symbol(symbol)
        fallbacks: list[FallbackRecord] = []
        last_error: ProviderError | None = None
        for index, provider in enumerate(self.providers):
            try:
                data = await provider.get_profile(normalized)
                return StockProfileResponse(
                    status="ok",
                    provider=provider.name,
                    provider_status="ok" if not fallbacks else "fallback",
                    fetched_at=datetime.now(UTC).isoformat(),
                    fallbacks=fallbacks,
                    data=data,
                )
            except ProviderError as exc:
                if not is_recoverable(exc.error_type) or index == len(self.providers) - 1:
                    raise
                next_provider = self.providers[index + 1]
                fallbacks.append(
                    FallbackRecord(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                        reason=exc.error_type.value,
                    )
                )
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("StockProfileService requires at least one provider.")
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/providers/test_tencent_profile.py tests/unit/services/test_stock_profile_service.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/providers/profile/tencent.py src/services/stock_profile_service.py tests/fixtures/tencent_quote.txt tests/unit/providers/test_tencent_profile.py tests/unit/services/test_stock_profile_service.py
git commit -m "feat: add tencent stock profile provider"
```

## Task 6: mootdx A-share K-line Provider

**Files:**
- Create: `src/providers/market_data/mootdx_kline.py`
- Modify: `src/services/stock_kline_service.py`
- Modify: `tests/unit/services/test_stock_kline_service.py`
- Create: `tests/unit/providers/test_mootdx_kline.py`

- [ ] **Step 1: Write failing provider tests for period mapping and datetime caveat**

Create `tests/unit/providers/test_mootdx_kline.py`:

```python
import pandas as pd
import pytest

from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.schemas import KlineRequest
from src.utils.symbols import normalize_symbol


class FakeQuotes:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def bars(self, **kwargs):
        self.calls.append(kwargs)
        return self.frame


@pytest.mark.asyncio
async def test_mootdx_provider_maps_daily_bars_and_drops_duplicate_datetime_column():
    frame = pd.DataFrame(
        {
            "datetime": ["2026-05-22"],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "vol": [1000],
            "amount": [2000],
        }
    )
    frame.index = pd.Index(["2026-05-22"], name="datetime")
    quotes = FakeQuotes(frame)
    provider = MootdxKlineProvider(quotes=quotes)

    data = await provider.get_kline(
        normalize_symbol("600519"),
        KlineRequest(symbol="600519", period="day", limit=1),
    )

    assert quotes.calls[0]["symbol"] == "600519"
    assert quotes.calls[0]["frequency"] == "day"
    assert quotes.calls[0]["offset"] == 1
    assert data.bars[0].date == "2026-05-22"
    assert data.bars[0].volume == 1000


@pytest.mark.asyncio
async def test_mootdx_provider_supports_quarter_as_three_month_frequency():
    frame = pd.DataFrame(
        {"datetime": ["2026-03-31"], "open": [1], "high": [1], "low": [1], "close": [1]}
    )
    quotes = FakeQuotes(frame)
    provider = MootdxKlineProvider(quotes=quotes)

    await provider.get_kline(
        normalize_symbol("600519"),
        KlineRequest(symbol="600519", period="quarter"),
    )

    assert quotes.calls[0]["frequency"] == "3mon"
```

- [ ] **Step 2: Add service tests for unsupported adjustment and provider success**

Append to `tests/unit/services/test_stock_kline_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest


class FakeAshareKlineProvider:
    name = "mootdx"

    async def get_kline(self, symbol, request):
        return KlineData(
            symbol=symbol,
            period=request.period,
            adjust=request.adjust,
            bars=[KlineBar(date="2026-05-22", open=1, high=2, low=1, close=2)],
        )


@pytest.mark.asyncio
async def test_a_share_kline_success_uses_configured_provider():
    service = StockKlineService(a_share_provider=FakeAshareKlineProvider(), hk_provider=None)

    response = await service.get_kline(KlineRequest(symbol="600519"))

    assert response.provider == "mootdx"
    assert response.data.bars[0].date == "2026-05-22"


@pytest.mark.asyncio
async def test_kline_rejects_unsupported_adjustment_before_provider_call():
    service = StockKlineService(a_share_provider=FakeAshareKlineProvider(), hk_provider=None)

    with pytest.raises(ProviderError) as raised:
        await service.get_kline(KlineRequest(symbol="600519", adjust="qfq"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_ADJUSTMENT
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/providers/test_mootdx_kline.py tests/unit/services/test_stock_kline_service.py -q
```

Expected: provider import error and service adjustment behavior failure.

- [ ] **Step 4: Implement the provider and service adjustment guard**

Create `src/providers/market_data/mootdx_kline.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd

from src.errors import ErrorType, ProviderError
from src.schemas import KlineBar, KlineData, KlineRequest
from src.utils.symbols import NormalizedSymbol


PERIOD_TO_MOOTDX_FREQUENCY = {
    "day": "day",
    "week": "week",
    "month": "mon",
    "quarter": "3mon",
    "year": "year",
}


class MootdxKlineProvider:
    name = "mootdx"

    def __init__(self, *, quotes: Any | None = None) -> None:
        if quotes is None:
            from mootdx.quotes import Quotes

            quotes = Quotes.factory(market="std")
        self.quotes = quotes

    async def get_kline(self, symbol: NormalizedSymbol, request: KlineRequest) -> KlineData:
        frequency = PERIOD_TO_MOOTDX_FREQUENCY[request.period]
        offset = request.limit or 800
        try:
            frame = await asyncio.to_thread(
                self.quotes.bars,
                symbol=symbol.symbol,
                frequency=frequency,
                offset=offset,
            )
        except Exception as exc:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=self.name,
                message=str(exc),
            ) from exc
        bars = _frame_to_bars(frame)
        if not bars:
            raise ProviderError(
                error_type=ErrorType.MARKET_CLOSED_OR_EMPTY,
                provider=self.name,
                message="mootdx returned no K-line bars.",
            )
        return KlineData(symbol=symbol, period=request.period, adjust=request.adjust, bars=bars)


def _frame_to_bars(frame: pd.DataFrame | None) -> list[KlineBar]:
    if frame is None or frame.empty:
        return []
    normalized = frame.copy()
    if "datetime" in normalized.columns and normalized.index.name == "datetime":
        normalized = normalized.drop(columns=["datetime"])
    normalized = normalized.reset_index()
    bars: list[KlineBar] = []
    for row in normalized.to_dict("records"):
        date_value = row.get("datetime") or row.get("date")
        bars.append(
            KlineBar(
                date=str(date_value)[:10],
                open=_float(row.get("open")),
                high=_float(row.get("high")),
                low=_float(row.get("low")),
                close=_float(row.get("close")),
                volume=_float(row.get("vol") if row.get("vol") is not None else row.get("volume")),
                amount=_float(row.get("amount")),
            )
        )
    return bars


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
```

Modify `StockKlineService.get_kline` before provider selection:

```python
        if request.adjust != "none":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_ADJUSTMENT,
                provider=None,
                message="Adjusted K-line data is not supported by the v1 default provider.",
            )
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/providers/test_mootdx_kline.py tests/unit/services/test_stock_kline_service.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/providers/market_data/mootdx_kline.py src/services/stock_kline_service.py tests/unit/providers/test_mootdx_kline.py tests/unit/services/test_stock_kline_service.py
git commit -m "feat: add mootdx kline provider"
```

## Task 7: Sina Financial Statements Provider And Service

**Files:**
- Create: `src/providers/financials/sina.py`
- Create: `src/services/financial_statement_service.py`
- Create: `tests/fixtures/sina_financial_report.json`
- Create: `tests/unit/providers/test_sina_financials.py`
- Create: `tests/unit/services/test_financial_statement_service.py`

- [ ] **Step 1: Add a compact Sina fixture**

Create `tests/fixtures/sina_financial_report.json`:

```json
{
  "result": {
    "data": {
      "report_count": 102,
      "report_date": [
        {"date_value": "20260331", "date_description": "2026一季报"}
      ],
      "report_list": {
        "20260331": {
          "f001": {
            "item_title": "营业总收入",
            "value": "17400000000",
            "display_type": "0",
            "group_num": "1",
            "yoy": "12.3"
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write failing provider tests**

Create `tests/unit/providers/test_sina_financials.py`:

```python
import json

import httpx
import pytest

from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_sina_maps_report_date_and_report_list_shape():
    fixture = json.loads(open("tests/fixtures/sina_financial_report.json", encoding="utf-8").read())

    async def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["paperCode"] == "sh600519"
        assert params["source"] == "lrb"
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SinaFinancialStatementsProvider(client=client)

    group = await provider.get_statement(normalize_symbol("600519"), "income", periods=1)

    assert group.statement_type == "income"
    assert group.periods[0].period == "20260331"
    assert group.periods[0].items[0].field_code == "f001"
    assert group.periods[0].items[0].title == "营业总收入"
```

- [ ] **Step 3: Write failing service tests**

Create `tests/unit/services/test_financial_statement_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import FinancialStatementGroup, FinancialStatementPeriod, FinancialStatementsRequest
from src.services.financial_statement_service import FinancialStatementService


class FakeFinancialProvider:
    name = "sina"

    async def get_statement(self, symbol, statement_type, periods):
        return FinancialStatementGroup(
            statement_type=statement_type,
            periods=[FinancialStatementPeriod(period="20260331", items=[])],
        )


@pytest.mark.asyncio
async def test_financial_service_rejects_hk_symbols():
    service = FinancialStatementService(provider=FakeFinancialProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_financial_statements(FinancialStatementsRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_financial_service_all_requests_three_statement_groups():
    service = FinancialStatementService(provider=FakeFinancialProvider())

    response = await service.get_financial_statements(FinancialStatementsRequest(symbol="600519"))

    assert [group.statement_type for group in response.data.statements] == [
        "balance_sheet",
        "income",
        "cash_flow",
    ]
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/providers/test_sina_financials.py tests/unit/services/test_financial_statement_service.py -q
```

Expected: import errors.

- [ ] **Step 5: Implement Sina provider and financial service**

Create `src/providers/financials/sina.py`:

```python
from __future__ import annotations

import httpx

from src.schemas import FinancialLineItem, FinancialStatementGroup, FinancialStatementPeriod
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol


SINA_SOURCE_BY_STATEMENT = {
    "income": "lrb",
    "balance_sheet": "fzb",
    "cash_flow": "llb",
}


class SinaFinancialStatementsProvider:
    name = "sina"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_statement(
        self,
        symbol: NormalizedSymbol,
        statement_type: str,
        periods: int,
    ) -> FinancialStatementGroup:
        source = SINA_SOURCE_BY_STATEMENT[statement_type]
        prefix = "sh" if symbol.exchange == "sh" else "sz"
        payload = await get_json(
            self.client,
            self.url,
            provider=self.name,
            params={
                "paperCode": f"{prefix}{symbol.symbol}",
                "source": source,
                "type": "0",
                "page": "1",
                "num": str(periods),
            },
        )
        data = ((payload.get("result") or {}).get("data") or {})
        report_dates = data.get("report_date") or []
        report_list = data.get("report_list") or {}
        mapped_periods: list[FinancialStatementPeriod] = []
        for report_date in report_dates[:periods]:
            period = report_date.get("date_value")
            raw_items = report_list.get(period) or {}
            mapped_periods.append(
                FinancialStatementPeriod(
                    period=str(period),
                    description=report_date.get("date_description"),
                    items=[
                        FinancialLineItem(
                            field_code=str(field_code),
                            title=str(item.get("item_title") or field_code),
                            value=item.get("value"),
                            display_type=item.get("display_type"),
                            group_number=item.get("group_num"),
                            source_statement_type=statement_type,
                            yoy_value=item.get("yoy"),
                        )
                        for field_code, item in raw_items.items()
                        if isinstance(item, dict)
                    ],
                )
            )
        return FinancialStatementGroup(statement_type=statement_type, periods=mapped_periods)
```

Create `src/services/financial_statement_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import (
    FinancialStatementsData,
    FinancialStatementsRequest,
    FinancialStatementsResponse,
)
from src.utils.symbols import normalize_symbol


ALL_STATEMENTS = ["balance_sheet", "income", "cash_flow"]


class FinancialStatementService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_financial_statements(
        self,
        request: FinancialStatementsRequest,
    ) -> FinancialStatementsResponse:
        symbol = normalize_symbol(request.symbol)
        if symbol.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Hong Kong financial statements are not supported in v1.",
            )
        statement_types = ALL_STATEMENTS if request.statement_type == "all" else [request.statement_type]
        groups = [
            await self.provider.get_statement(symbol, statement_type, request.periods)
            for statement_type in statement_types
        ]
        return FinancialStatementsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=FinancialStatementsData(symbol=symbol, statements=groups),
        )
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/providers/test_sina_financials.py tests/unit/services/test_financial_statement_service.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/providers/financials/sina.py src/services/financial_statement_service.py tests/fixtures/sina_financial_report.json tests/unit/providers/test_sina_financials.py tests/unit/services/test_financial_statement_service.py
git commit -m "feat: add sina financial statements provider"
```

## Task 8: F10, Announcements, And Research Report Providers

**Files:**
- Create: `src/providers/f10/mootdx_f10.py`
- Create: `src/providers/announcements/cninfo.py`
- Create: `src/providers/research/eastmoney.py`
- Create: `src/services/stock_f10_service.py`
- Create: `src/services/announcement_service.py`
- Create: `src/services/research_report_service.py`
- Create: `tests/fixtures/cninfo_announcements.json`
- Create: `tests/fixtures/eastmoney_research_reports.json`
- Create: provider and service tests listed in the file structure

- [ ] **Step 1: Add announcement and research fixtures**

Create `tests/fixtures/cninfo_announcements.json`:

```json
{
  "announcements": [
    {
      "announcementTitle": "2025年年度报告",
      "announcementTypeName": "年度报告",
      "announcementTime": 1777046400000,
      "announcementId": "1210000000",
      "adjunctUrl": "finalpage/2026-04-25/1210000000.PDF"
    }
  ]
}
```

Create `tests/fixtures/eastmoney_research_reports.json`:

```json
{
  "TotalPage": 1,
  "data": [
    {
      "title": "公司深度报告",
      "publishDate": "2026-05-22T00:00:00",
      "orgSName": "示例证券",
      "emRatingName": "买入",
      "industryName": "白酒",
      "predictThisYearEps": "50.1",
      "predictNextYearEps": "55.2",
      "infoCode": "AP202605220000001"
    }
  ]
}
```

- [ ] **Step 2: Write failing provider tests**

Create `tests/unit/providers/test_mootdx_f10.py`:

```python
import pytest

from src.providers.f10.mootdx_f10 import MootdxF10Provider
from src.utils.symbols import normalize_symbol


class FakeQuotes:
    def __init__(self):
        self.calls = []

    def F10(self, **kwargs):
        self.calls.append(kwargs)
        return "公司概况正文"


@pytest.mark.asyncio
async def test_f10_maps_english_section_to_chinese_name():
    quotes = FakeQuotes()
    provider = MootdxF10Provider(quotes=quotes)

    text = await provider.get_f10(normalize_symbol("600519"), "company_profile")

    assert text == "公司概况正文"
    assert quotes.calls[0]["name"] == "公司概况"
```

Create `tests/unit/providers/test_cninfo_announcements.py`:

```python
import json

import httpx
import pytest

from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_cninfo_maps_announcement_fields():
    fixture = json.loads(open("tests/fixtures/cninfo_announcements.json", encoding="utf-8").read())

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CninfoAnnouncementProvider(client=client)

    items = await provider.get_announcements(normalize_symbol("600519"), page_size=20)

    assert items[0].title == "2025年年度报告"
    assert items[0].announcement_type == "年度报告"
    assert items[0].url == "https://static.cninfo.com.cn/finalpage/2026-04-25/1210000000.PDF"
```

Create `tests/unit/providers/test_eastmoney_research.py`:

```python
import json

import httpx
import pytest

from src.providers.research.eastmoney import EastmoneyResearchReportProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_eastmoney_maps_research_report_fields():
    fixture = json.loads(open("tests/fixtures/eastmoney_research_reports.json", encoding="utf-8").read())

    async def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params)["code"] == "600519"
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = EastmoneyResearchReportProvider(client=client)

    reports = await provider.get_reports(normalize_symbol("600519"), page_size=20)

    assert reports[0].title == "公司深度报告"
    assert reports[0].institution == "示例证券"
    assert reports[0].eps_forecast["predict_this_year_eps"] == "50.1"
    assert reports[0].pdf_url.endswith("AP202605220000001.pdf")
```

- [ ] **Step 3: Write failing service tests**

Create `tests/unit/services/test_stock_f10_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.services.stock_f10_service import StockF10Service


class FakeF10Provider:
    name = "mootdx"

    async def get_f10(self, symbol, section):
        return "x" * 20


@pytest.mark.asyncio
async def test_f10_service_rejects_hk_symbols():
    service = StockF10Service(provider=FakeF10Provider())

    with pytest.raises(ProviderError) as raised:
        await service.get_f10("00700", section="company_profile", max_chars=10)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_f10_service_truncates_long_text():
    service = StockF10Service(provider=FakeF10Provider())

    response = await service.get_f10("600519", section="company_profile", max_chars=10)

    assert response.data.text == "x" * 10
    assert response.data.truncated is True
    assert response.data.provider_section == "公司概况"
```

Create `tests/unit/services/test_announcement_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.services.announcement_service import AnnouncementService


class FakeAnnouncementProvider:
    name = "cninfo"

    async def get_announcements(self, symbol, page_size):
        return []


@pytest.mark.asyncio
async def test_announcement_service_rejects_hk_symbols():
    service = AnnouncementService(provider=FakeAnnouncementProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_announcements("00700", page_size=20)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_announcement_service_returns_a_share_response():
    service = AnnouncementService(provider=FakeAnnouncementProvider())

    response = await service.get_announcements("600519", page_size=20)

    assert response.provider == "cninfo"
    assert response.data.symbol.display_symbol == "600519.SH"
```

Create `tests/unit/services/test_research_report_service.py`:

```python
import pytest

from src.errors import ErrorType, ProviderError
from src.services.research_report_service import ResearchReportService


class FakeResearchProvider:
    name = "eastmoney"

    async def get_reports(self, symbol, page_size):
        return []


@pytest.mark.asyncio
async def test_research_report_service_rejects_hk_symbols():
    service = ResearchReportService(provider=FakeResearchProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_reports("00700", page_size=20)

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_research_report_service_returns_a_share_response():
    service = ResearchReportService(provider=FakeResearchProvider())

    response = await service.get_reports("600519", page_size=20)

    assert response.provider == "eastmoney"
    assert response.data.symbol.display_symbol == "600519.SH"
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit/providers/test_mootdx_f10.py tests/unit/providers/test_cninfo_announcements.py tests/unit/providers/test_eastmoney_research.py tests/unit/services/test_stock_f10_service.py tests/unit/services/test_announcement_service.py tests/unit/services/test_research_report_service.py -q
```

Expected: import errors.

- [ ] **Step 5: Implement the providers and services**

Create `src/providers/f10/mootdx_f10.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

from src.errors import ErrorType, ProviderError
from src.utils.symbols import NormalizedSymbol


SECTION_MAP = {
    "company_profile": "公司概况",
    "latest_notice": "最新提示",
    "shareholders": "股东研究",
    "capital_structure": "股本结构",
    "financial_analysis": "财务分析",
}


class MootdxF10Provider:
    name = "mootdx"

    def __init__(self, *, quotes: Any | None = None) -> None:
        if quotes is None:
            from mootdx.quotes import Quotes

            quotes = Quotes.factory(market="std")
        self.quotes = quotes

    async def get_f10(self, symbol: NormalizedSymbol, section: str) -> str:
        provider_section = SECTION_MAP[section]
        try:
            text = await asyncio.to_thread(
                self.quotes.F10,
                symbol=symbol.symbol,
                name=provider_section,
            )
        except Exception as exc:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_ERROR,
                provider=self.name,
                message=str(exc),
            ) from exc
        return text or ""
```

Create `src/providers/announcements/cninfo.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from src.schemas import AnnouncementItem
from src.utils.http import post_form_json
from src.utils.symbols import NormalizedSymbol


CNINFO_BASE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"


class CninfoAnnouncementProvider:
    name = "cninfo"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_announcements(
        self,
        symbol: NormalizedSymbol,
        page_size: int,
    ) -> list[AnnouncementItem]:
        payload = await post_form_json(
            self.client,
            CNINFO_BASE_URL,
            provider=self.name,
            data={
                "stock": f"{symbol.symbol},{_org_id(symbol)}",
                "tabName": "fulltext",
                "pageSize": str(page_size),
                "pageNum": "1",
                "column": "",
                "category": "",
                "plate": "",
                "seDate": "",
                "searchkey": "",
                "secid": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.cninfo.com.cn/new/disclosure",
                "Origin": "https://www.cninfo.com.cn",
            },
        )
        return [_map_announcement(item) for item in payload.get("announcements") or []]


def _org_id(symbol: NormalizedSymbol) -> str:
    if symbol.exchange == "sh":
        return f"gssh0{symbol.symbol}"
    if symbol.exchange == "bj":
        return f"gsbj0{symbol.symbol}"
    return f"gssz0{symbol.symbol}"


def _map_announcement(item: dict[str, Any]) -> AnnouncementItem:
    adjunct_url = item.get("adjunctUrl")
    return AnnouncementItem(
        title=item.get("announcementTitle"),
        announcement_type=item.get("announcementTypeName"),
        date=_date_from_millis(item.get("announcementTime")),
        announcement_id=item.get("announcementId"),
        url=f"{CNINFO_STATIC_BASE}{adjunct_url}" if adjunct_url else None,
    )


def _date_from_millis(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None
```

Create `src/providers/research/eastmoney.py`:

```python
from __future__ import annotations

from typing import Any

import httpx

from src.schemas import ResearchReportItem
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol


EASTMONEY_REPORT_URL = "https://reportapi.eastmoney.com/report/list"
PDF_BASE_URL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"


class EastmoneyResearchReportProvider:
    name = "eastmoney"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_reports(
        self,
        symbol: NormalizedSymbol,
        page_size: int,
    ) -> list[ResearchReportItem]:
        payload = await get_json(
            self.client,
            EASTMONEY_REPORT_URL,
            provider=self.name,
            params={
                "industryCode": "*",
                "pageSize": str(page_size),
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": "1",
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": symbol.symbol,
                "rcode": "",
                "p": "1",
                "pageNum": "1",
                "pageNumber": "1",
            },
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"},
        )
        return [_map_report(item) for item in payload.get("data") or []]


def _map_report(item: dict[str, Any]) -> ResearchReportItem:
    info_code = item.get("infoCode")
    return ResearchReportItem(
        title=item.get("title"),
        publish_date=str(item.get("publishDate") or "")[:10] or None,
        institution=item.get("orgSName"),
        rating=item.get("emRatingName"),
        industry=item.get("industryName"),
        eps_forecast={
            "predict_this_year_eps": item.get("predictThisYearEps"),
            "predict_next_year_eps": item.get("predictNextYearEps"),
        },
        info_code=info_code,
        pdf_url=PDF_BASE_URL.format(info_code=info_code) if info_code else None,
    )
```

Create `src/services/stock_f10_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.providers.f10.mootdx_f10 import SECTION_MAP
from src.schemas import F10Data, F10Response
from src.utils.symbols import normalize_symbol


class StockF10Service:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_f10(self, symbol: str, *, section: str, max_chars: int) -> F10Response:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="F10 is supported for A-shares only in v1.",
            )
        text = await self.provider.get_f10(normalized, section)
        truncated = len(text) > max_chars
        return F10Response(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=F10Data(
                symbol=normalized,
                section=section,
                provider_section=SECTION_MAP[section],
                text=text[:max_chars],
                truncated=truncated,
            ),
        )
```

Create `src/services/announcement_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import AnnouncementsData, AnnouncementsResponse
from src.utils.symbols import normalize_symbol


class AnnouncementService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_announcements(self, symbol: str, *, page_size: int) -> AnnouncementsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Announcements are supported for A-shares only in v1.",
            )
        announcements = await self.provider.get_announcements(normalized, page_size)
        return AnnouncementsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=AnnouncementsData(symbol=normalized, announcements=announcements),
        )
```

Create `src/services/research_report_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import ResearchReportsData, ResearchReportsResponse
from src.utils.symbols import normalize_symbol


class ResearchReportService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_reports(self, symbol: str, *, page_size: int) -> ResearchReportsResponse:
        normalized = normalize_symbol(symbol)
        if normalized.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Research reports are supported for A-shares only in v1.",
            )
        reports = await self.provider.get_reports(normalized, page_size)
        return ResearchReportsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=ResearchReportsData(symbol=normalized, reports=reports),
        )
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/providers/test_mootdx_f10.py tests/unit/providers/test_cninfo_announcements.py tests/unit/providers/test_eastmoney_research.py tests/unit/services/test_stock_f10_service.py tests/unit/services/test_announcement_service.py tests/unit/services/test_research_report_service.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/providers/f10 src/providers/announcements src/providers/research src/services/stock_f10_service.py src/services/announcement_service.py src/services/research_report_service.py tests/fixtures tests/unit/providers tests/unit/services
git commit -m "feat: add f10 announcements and research providers"
```

## Task 9: MCP Tools And Resources

**Files:**
- Modify: `src/api/mcp_full.py`
- Create: `src/resources/tool_guides.py`
- Create: `src/resources/stock-tools-guide.md`
- Create: `src/resources/providers-capabilities.md`
- Create: `tests/unit/api/test_mcp_full.py`

- [ ] **Step 1: Write failing MCP and resource tests**

Create `tests/unit/api/test_mcp_full.py`:

```python
import pytest

from src.api.mcp_full import create_mcp_server
from src.resources.tool_guides import RESOURCE_URIS, load_resource_text, resource_text_by_uri


def test_resource_markdown_files_load():
    assert "stock_kline" in load_resource_text("stock-tools-guide.md")
    assert "Tencent" in load_resource_text("providers-capabilities.md")
    assert "agenteum-fin://tools/stock-tools-guide" in RESOURCE_URIS


def test_resource_text_by_uri_loads_known_resource():
    text = resource_text_by_uri("agenteum-fin://providers/capabilities")

    assert "Hong Kong K-line" in text


@pytest.mark.asyncio
async def test_mcp_server_can_be_created_with_fake_services():
    mcp = create_mcp_server(
        kline_service=object(),
        profile_service=object(),
        financial_service=object(),
        f10_service=object(),
        announcement_service=object(),
        research_report_service=object(),
    )

    assert mcp.name == "Agenteum Fin"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py -q
```

Expected: resource import failures and incomplete MCP implementation.

- [ ] **Step 3: Implement resources**

Create `src/resources/tool_guides.py`:

```python
from __future__ import annotations

from importlib.resources import files


RESOURCE_URIS = {
    "agenteum-fin://tools/stock-tools-guide": "stock-tools-guide.md",
    "agenteum-fin://providers/capabilities": "providers-capabilities.md",
}


def load_resource_text(filename: str) -> str:
    return files("src.resources").joinpath(filename).read_text(encoding="utf-8")


def resource_text_by_uri(uri: str) -> str:
    return load_resource_text(RESOURCE_URIS[uri])
```

Create `src/resources/stock-tools-guide.md`:

```markdown
# Agenteum Fin Stock Tools

Tools: stock_kline, stock_profile, stock_financial_statements, stock_f10, stock_announcements, stock_research_reports.

Use stock_kline for daily and higher-period OHLCV bars. Hong Kong K-line returns unsupported_market in v1 unless a verified provider is configured in a later version.

Use stock_profile for lightweight quote and valuation fields. Tencent A-share amount is normalized from ten-thousand CNY units; Tencent Hong Kong amount is HKD when usable.

Use stock_financial_statements for A-share balance sheet, income statement, and cash flow statement data from Sina.
```

Create `src/resources/providers-capabilities.md`:

```markdown
# Provider Capabilities

- mootdx: default A-share K-line and F10 provider.
- Tencent quote: default A-share and Hong Kong profile quote provider.
- Sina: default A-share financial statements provider.
- cninfo: default A-share announcements provider.
- Eastmoney reportapi: default A-share research reports provider.
- Hong Kong K-line: unsupported_market in v1 because no stable provider passed the checkpoint.
- Hong Kong financial statements, announcements, and research reports: unsupported_market in v1.
```

- [ ] **Step 4: Implement MCP tool registration**

Replace `src/api/mcp_full.py` with:

```python
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.errors import ProviderError, is_recoverable
from src.resources.tool_guides import RESOURCE_URIS, resource_text_by_uri
from src.schemas import (
    ErrorDetail,
    F10Request,
    FinancialStatementsRequest,
    KlineRequest,
    ToolErrorResponse,
)


def create_mcp_server(
    *,
    kline_service: Any | None = None,
    profile_service: Any | None = None,
    financial_service: Any | None = None,
    f10_service: Any | None = None,
    announcement_service: Any | None = None,
    research_report_service: Any | None = None,
) -> FastMCP:
    mcp = FastMCP(
        "Agenteum Fin",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )

    @mcp.tool()
    async def stock_kline(
        symbol: str,
        period: str = "day",
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "none",
        limit: int | None = None,
    ) -> dict:
        """Return daily or higher-period OHLCV K-line bars."""
        try:
            request = KlineRequest(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
                limit=limit,
            )
            response = await kline_service.get_kline(request)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_profile(symbol: str) -> dict:
        """Return lightweight structured stock profile, quote, and valuation fields."""
        try:
            response = await profile_service.get_profile(symbol)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_financial_statements(
        symbol: str,
        statement_type: str = "all",
        periods: int = 8,
    ) -> dict:
        """Return A-share balance sheet, income statement, and cash flow statement data."""
        try:
            request = FinancialStatementsRequest(
                symbol=symbol,
                statement_type=statement_type,
                periods=periods,
            )
            response = await financial_service.get_financial_statements(request)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_f10(
        symbol: str,
        section: str = "company_profile",
        max_chars: int = 4000,
    ) -> dict:
        """Return bounded A-share F10 text sections."""
        try:
            request = F10Request(symbol=symbol, section=section, max_chars=max_chars)
            response = await f10_service.get_f10(
                request.symbol,
                section=request.section,
                max_chars=request.max_chars,
            )
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_announcements(symbol: str, page_size: int = 20) -> dict:
        """Return A-share listed-company announcements."""
        try:
            response = await announcement_service.get_announcements(symbol, page_size=page_size)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    @mcp.tool()
    async def stock_research_reports(symbol: str, page_size: int = 20) -> dict:
        """Return A-share sell-side research report metadata."""
        try:
            response = await research_report_service.get_reports(symbol, page_size=page_size)
            return response.model_dump(by_alias=True)
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)

    for uri in RESOURCE_URIS:
        _register_resource(mcp, uri)

    return mcp


def _provider_error_response(exc: ProviderError) -> ToolErrorResponse:
    return ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type=exc.error_type.value,
            message=exc.message,
            provider=exc.provider,
            retryable=is_recoverable(exc.error_type),
        ),
        fallbacks=[],
    )


def _register_resource(mcp: FastMCP, uri: str) -> None:
    @mcp.resource(uri)
    def read_resource() -> str:
        return resource_text_by_uri(uri)
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/api/mcp_full.py src/resources tests/unit/api/test_mcp_full.py
git commit -m "feat: expose agenteum fin mcp tools"
```

## Task 10: Wire Real Services Into App

**Files:**
- Modify: `src/app.py`
- Modify: `tests/smoke/test_mcp_http.py`

- [ ] **Step 1: Extend smoke test for full app wiring**

Append to `tests/smoke/test_mcp_http.py`:

```python
def test_create_app_with_default_settings_does_not_call_live_providers():
    app = create_app(Settings())

    assert app.title == "Agenteum Fin"
```

- [ ] **Step 2: Run smoke tests and verify they pass before wiring change**

Run:

```powershell
uv run pytest tests/smoke/test_mcp_http.py -q
```

Expected: tests pass because app creation should not call live providers.

- [ ] **Step 3: Wire configured providers and services**

Modify `src/app.py` imports and `create_app` body so it creates:

```python
from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.providers.f10.mootdx_f10 import MootdxF10Provider
from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.providers.profile.tencent import TencentProfileProvider
from src.providers.research.eastmoney import EastmoneyResearchReportProvider
from src.services.announcement_service import AnnouncementService
from src.services.financial_statement_service import FinancialStatementService
from src.services.research_report_service import ResearchReportService
from src.services.stock_f10_service import StockF10Service
from src.services.stock_kline_service import StockKlineService
from src.services.stock_profile_service import StockProfileService
```

Inside `create_app`:

```python
    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)

    kline_service = StockKlineService(
        a_share_provider=MootdxKlineProvider(),
        hk_provider=None,
    )
    profile_service = StockProfileService(providers=[TencentProfileProvider(client=http_client)])
    financial_service = FinancialStatementService(
        provider=SinaFinancialStatementsProvider(client=http_client),
    )
    f10_service = StockF10Service(provider=MootdxF10Provider())
    announcement_service = AnnouncementService(
        provider=CninfoAnnouncementProvider(client=http_client),
    )
    research_report_service = ResearchReportService(
        provider=EastmoneyResearchReportProvider(client=http_client),
    )

    mcp = create_mcp_server(
        kline_service=kline_service,
        profile_service=profile_service,
        financial_service=financial_service,
        f10_service=f10_service,
        announcement_service=announcement_service,
        research_report_service=research_report_service,
    )
```

Keep the lifespan `await http_client.aclose()` cleanup.

- [ ] **Step 4: Run smoke tests**

Run:

```powershell
uv run pytest tests/smoke/test_mcp_http.py -q
```

Expected: all smoke tests pass without live provider calls.

- [ ] **Step 5: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add src/app.py tests/smoke/test_mcp_http.py
git commit -m "feat: wire configured services into app"
```

## Task 11: opencode E2E Test

**Files:**
- Create: `tests/e2e/test_opencode_mcp.py`

- [ ] **Step 1: Write the E2E test**

Create `tests/e2e/test_opencode_mcp.py`. Base it on `D:\workspace\agenteum\agenteum-net\tests\e2e\test_opencode_mcp.py` with these Agenteum Fin changes:

```python
SERVER_START_TIMEOUT = 15.0
OPENCODE_TIMEOUT = 120.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

Start the server with:

```python
proc = subprocess.Popen(
    [uv, "run", "agenteum-fin"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=str(PROJECT_ROOT),
    env={
        **dict(subprocess.os.environ),
        "AGENTEUM_HOST": "127.0.0.1",
        "AGENTEUM_PORT": str(server_port),
        "AGENTEUM_ALLOW_REMOTE": "false",
    },
)
```

Test `opencode --pure mcp list`:

```python
if "agenteum-fin" not in combined:
    pytest.skip("opencode is not configured with agenteum-fin MCP; user config is not modified by tests")
assert "connected" in combined.lower()
```

Test tool invocation with this prompt:

```python
prompt = "请通过 agenteum-fin 查询 600519 的 stock_profile，只需要调用工具并返回结果摘要"
```

Parse JSON events and assert:

```python
tool_event = _find_tool_use_event(events, "stock_profile")
assert tool_event is not None
tool_input = tool_event.get("part", {}).get("state", {}).get("input", {})
assert tool_input.get("symbol") in {"600519", "SH600519", "600519.SH"}
```

- [ ] **Step 2: Run the E2E test**

Run:

```powershell
uv run pytest tests/e2e/test_opencode_mcp.py -q
```

Expected when `opencode` and model credentials are available: tests pass and opencode shows `agenteum-fin connected`.

Expected when `opencode` is not installed: pytest skips with `opencode not found in PATH`.

Expected when `opencode` is installed but not already configured for `agenteum-fin`: pytest skips without editing `~/.config/opencode/opencode.jsonc`.

- [ ] **Step 3: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add tests/e2e/test_opencode_mcp.py
git commit -m "test: add opencode mcp e2e coverage"
```

## Task 12: Documentation And Provider Capabilities Final Pass

**Files:**
- Modify: `README.md`
- Modify: `src/resources/stock-tools-guide.md`
- Modify: `src/resources/providers-capabilities.md`
- Verify: `.env.example`

- [ ] **Step 1: Update README with run and test commands**

Add this content to `README.md`:

````markdown
## Run

```powershell
uv run agenteum-fin
```

The server listens on `http://127.0.0.1:8766` by default and exposes MCP at `/mcp/full`.

## Test

```powershell
uv run pytest -q
uv run ruff check .
```

Default tests use fixtures and fake providers. Live provider probes live in `playground/provider_probe.py`.

## Provider Switching

Provider selection is static for a running process. Change `.env`, then restart the server.
````

- [ ] **Step 2: Ensure resources match v1 limitations**

Verify `src/resources/providers-capabilities.md` contains these exact statements:

```markdown
- Hong Kong K-line: unsupported_market in v1 because no stable provider passed the checkpoint.
- Hong Kong financial statements, announcements, and research reports: unsupported_market in v1.
- Adjusted K-line modes qfq and hfq: unsupported_adjustment for the default v1 provider.
```

- [ ] **Step 3: Run resource and README checks**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit or record changed files**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git add README.md src/resources .env.example
git commit -m "docs: document agenteum fin v1 capabilities"
```

## Task 13: Full Verification

**Files:**
- No new files
- Verify all files created by previous tasks

- [ ] **Step 1: Run unit and smoke tests**

Run:

```powershell
uv run pytest tests/unit tests/smoke -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run:

```powershell
uv run ruff check .
```

Expected: no lint failures.

- [ ] **Step 3: Run opencode E2E**

Run:

```powershell
uv run pytest tests/e2e/test_opencode_mcp.py -q
```

Expected: pass when opencode and model credentials are configured; skip only when opencode is unavailable.

- [ ] **Step 4: Run manual live provider probe**

Run:

```powershell
uv run python playground/provider_probe.py
```

Expected: probe writes `playground/provider_probe_results.json`; live provider failures are documented rather than treated as default test failures.

- [ ] **Step 5: Run Claude non-interactive review**

Run:

```powershell
claude -p "Review this Agenteum Fin v1 implementation against docs/superpowers/specs/2026-05-22-agenteum-fin-design.md. Focus on bugs, provider mapping mistakes, MCP integration issues, tests, and scope creep. Return findings ordered by severity with file paths and line numbers." --output-format text
```

Expected: Claude returns either no blocking findings or actionable findings. Fix blocking findings before completing the branch.

If review needs a follow-up after fixes, continue the same session:

```powershell
claude --continue -p "I fixed the previous findings. Re-review the changed implementation against the same v1 design spec, focusing only on remaining blocking issues." --output-format text
```

- [ ] **Step 6: Final acceptance checklist**

Verify each item is true:

```text
/mcp/full exists.
/health returns {"status":"ok"}.
Six MCP tools are registered.
A-share stock_profile maps Tencent fields with normalized volume and amount.
Hong Kong stock_profile maps Tencent fields and returns PB/turnover_rate as null unless verified.
A-share stock_kline uses mootdx and handles duplicate datetime safely.
Hong Kong stock_kline returns unsupported_market.
A-share stock_financial_statements uses Sina report_date/report_list.
Hong Kong stock_financial_statements returns unsupported_market.
F10 section mapping uses the explicit English-to-Chinese map.
Announcements use cninfo.
Research reports use Eastmoney reportapi.
Default tests do not call live finance providers.
opencode E2E proves a coding agent can discover and invoke the MCP tools.
```

- [ ] **Step 7: Commit or record verification state**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected in current workspace: non-zero exit.

When running inside a git repository:

```powershell
git status --short
git add .
git commit -m "test: verify agenteum fin v1"
```

## Self-Review Notes

- Spec coverage: the plan covers project scaffold, config, symbols, schemas, error model, logging-safe provider errors, provider boundaries, A-share K-line, profile, financial statements, F10, announcements, research reports, Hong Kong unsupported behavior, resources, `/mcp/full`, `/health`, unit tests, smoke tests, opencode E2E, live POC, and Claude non-interactive review.
- Roadmap scope: stock news, shareholder count, institution consensus EPS, hot topics, concept blocks, margin trading, US stocks, crypto, macro data, and Hong Kong financial statements remain outside v1 and in `docs/future-requirements.md`.
- Provider decision: Hong Kong K-line remains `unsupported_market` in this implementation plan because no stable provider passed the recorded POC.
