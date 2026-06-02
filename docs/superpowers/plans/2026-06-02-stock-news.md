# Stock News Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `stock_news` MCP tool that searches Google News, Twitter/X, and Xueqiu through `opencli`.

**Architecture:** Keep the approved service-only design: `StockNewsService` owns symbol classification, profile-name enrichment, query construction, subprocess execution, JSON parsing, and partial-failure response assembly. The MCP API layer validates inputs with Pydantic and serializes service responses like the existing tools.

**Tech Stack:** Python 3.11, Pydantic v2, asyncio subprocesses, pytest, pytest-asyncio, Ruff, official MCP Python SDK.

**Post-plan correction:** Live validation showed Xueqiu Hong Kong comments should use the bare five-digit symbol, for example `00700`, not `HK00700`. Twitter/X queries should use the company name only when enrichment is available and append `, since:YYYY-MM-DD`, for example `快手-W, since:2026-05-26`.

---

## Precondition

The current Codex session can write workspace files but cannot write `.git`, so commit commands will fail here until the session or sandbox grants Git metadata write access. Keep the commit steps in the plan and run them in a Git-writable session using the required repository author format.

## File Structure

- Create `src/services/stock_news_service.py`: service-only `opencli` wrapper, command runner, symbol/query construction, and partial-failure aggregation.
- Modify `src/schemas.py`: add `StockNewsRequest`, `StockNewsData`, and `StockNewsResponse`.
- Modify `src/provider_factory.py`: build one `StockNewsService` using the existing profile service.
- Modify `src/api/mcp_full.py`: add `stock_news` tool registration and structured error handling.
- Modify `src/app.py`: pass `news_service` into `create_mcp_server`.
- Modify `src/resources/stock-tools-guide.md`: document `stock_news`.
- Modify `src/resources/providers-capabilities.md`: document `opencli` as an external CLI dependency.
- Create `tests/unit/services/test_stock_news_service.py`: service-level TDD coverage with fake command runner.
- Modify `tests/unit/test_schemas.py`: schema validation and serialization coverage.
- Modify `tests/unit/api/test_mcp_full.py`: MCP tool coverage.
- Modify `tests/unit/test_provider_factory.py`: service bundle wiring coverage.

### Task 1: Stock News Schemas

**Files:**
- Modify: `src/schemas.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

Append these imports to `tests/unit/test_schemas.py`:

```python
    StockNewsData,
    StockNewsRequest,
    StockNewsResponse,
```

Append these tests to `tests/unit/test_schemas.py`:

```python
def test_stock_news_request_defaults_to_week_range():
    request = StockNewsRequest(symbol="600519")

    assert request.symbol == "600519"
    assert request.time_range == "w"


def test_stock_news_request_rejects_unknown_time_range():
    with pytest.raises(ValidationError):
        StockNewsRequest(symbol="600519", time_range="year")


def test_stock_news_response_allows_partial_null_sources():
    response = StockNewsResponse(
        data=StockNewsData(
            google=[{"title": "贵州茅台新闻"}],
            twitter=None,
            xueqiu={"comments": []},
        )
    )

    dumped = response.model_dump()

    assert dumped == {
        "status": "ok",
        "data": {
            "google": [{"title": "贵州茅台新闻"}],
            "twitter": None,
            "xueqiu": {"comments": []},
        },
    }
```

- [ ] **Step 2: Run the schema tests to verify they fail**

Run:

```powershell
uv run pytest tests/unit/test_schemas.py::test_stock_news_request_defaults_to_week_range tests/unit/test_schemas.py::test_stock_news_request_rejects_unknown_time_range tests/unit/test_schemas.py::test_stock_news_response_allows_partial_null_sources -v
```

Expected: FAIL with `ImportError: cannot import name 'StockNewsData'` or `NameError` for the missing schema classes.

- [ ] **Step 3: Add the schema implementation**

Add these classes to `src/schemas.py` after `ResearchReportsResponse`:

```python
class StockNewsRequest(BaseModel):
    symbol: str
    time_range: Literal["w", "d", "m"] = "w"


class StockNewsData(BaseModel):
    google: Any | None = None
    twitter: Any | None = None
    xueqiu: Any | None = None


class StockNewsResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: StockNewsData
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run:

```powershell
uv run pytest tests/unit/test_schemas.py::test_stock_news_request_defaults_to_week_range tests/unit/test_schemas.py::test_stock_news_request_rejects_unknown_time_range tests/unit/test_schemas.py::test_stock_news_response_allows_partial_null_sources -v
```

Expected: PASS for all three tests.

- [ ] **Step 5: Commit the schema task**

Run in a Git-writable session:

```powershell
git add src/schemas.py tests/unit/test_schemas.py
git commit --author="Codex <codex@agenteum.com>" -m "feat: add stock news schemas"
```

### Task 2: Stock News Service

**Files:**
- Create: `src/services/stock_news_service.py`
- Create: `tests/unit/services/test_stock_news_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `tests/unit/services/test_stock_news_service.py` with this content:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import StockProfileData, StockProfileResponse
from src.services.stock_news_service import OpenCliCommandResult, StockNewsService
from src.utils.symbols import normalize_symbol


class FakeProfileService:
    def __init__(self, *, name: str | None = "贵州茅台", error: ProviderError | None = None):
        self.name = name
        self.error = error
        self.calls: list[str] = []

    async def get_profile(self, symbol: str) -> StockProfileResponse:
        self.calls.append(symbol)
        if self.error is not None:
            raise self.error
        return StockProfileResponse(
            status="ok",
            provider="tencent",
            provider_status="ok",
            fetched_at="2026-06-02T00:00:00+00:00",
            fallbacks=[],
            data=StockProfileData(symbol=normalize_symbol(symbol), name=self.name),
        )


class RecordingRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[tuple[list[str], dict[str, str], float]] = []

    async def __call__(
        self,
        command: list[str],
        env: dict[str, str],
        timeout_seconds: float,
    ) -> OpenCliCommandResult:
        self.calls.append((command, env, timeout_seconds))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def fixed_now() -> datetime:
    return datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


def ok_result(payload: str) -> OpenCliCommandResult:
    return OpenCliCommandResult(returncode=0, stdout=payload, stderr="")


@pytest.mark.asyncio
async def test_get_news_enriches_a_share_and_builds_opencli_commands():
    runner = RecordingRunner(
        [
            ok_result('[{"title": "google"}]'),
            ok_result('{"posts": ["twitter"]}'),
            ok_result('{"comments": ["xueqiu"]}'),
        ]
    )
    profile = FakeProfileService(name="贵州茅台")
    service = StockNewsService(profile_service=profile, command_runner=runner, now=fixed_now)

    response = await service.get_news("SH600519", time_range="w")

    assert response.status == "ok"
    assert response.data.google == [{"title": "google"}]
    assert response.data.twitter == {"posts": ["twitter"]}
    assert response.data.xueqiu == {"comments": ["xueqiu"]}
    assert profile.calls == ["SH600519"]
    assert runner.calls[0][0] == [
        "opencli",
        "google",
        "news",
        "600519.SH 贵州茅台",
        "--lang",
        "zh",
        "--region",
        "CN",
        "-f",
        "json",
    ]
    assert runner.calls[1][0] == [
        "opencli",
        "twitter",
        "search",
        "600519.SH 贵州茅台 since:2026-05-26",
        "--product",
        "live",
        "--limit",
        "30",
        "-f",
        "json",
    ]
    assert runner.calls[2][0] == [
        "opencli",
        "xueqiu",
        "comments",
        "SH600519",
        "-f",
        "json",
    ]
    assert all(call[1]["NODE_NO_WARNINGS"] == "1" for call in runner.calls)
    assert all(call[2] == 30.0 for call in runner.calls)


@pytest.mark.asyncio
async def test_get_news_uses_display_symbol_when_profile_lookup_fails():
    runner = RecordingRunner(
        [
            ok_result("[]"),
            ok_result("[]"),
            ok_result("[]"),
        ]
    )
    profile = FakeProfileService(
        error=ProviderError(
            error_type=ErrorType.PROVIDER_ERROR,
            provider="tencent",
            message="profile failed",
        )
    )
    service = StockNewsService(profile_service=profile, command_runner=runner, now=fixed_now)

    response = await service.get_news("00700", time_range="d")

    assert response.status == "ok"
    assert profile.calls == ["00700"]
    assert runner.calls[0][0][3] == "00700.HK"
    assert runner.calls[1][0][3] == "00700.HK since:2026-06-01"
    assert runner.calls[2][0] == ["opencli", "xueqiu", "comments", "HK00700", "-f", "json"]


@pytest.mark.asyncio
async def test_get_news_accepts_us_tickers_without_profile_lookup():
    runner = RecordingRunner(
        [
            ok_result("[]"),
            ok_result("[]"),
            ok_result("[]"),
        ]
    )
    profile = FakeProfileService(name="Apple")
    service = StockNewsService(profile_service=profile, command_runner=runner, now=fixed_now)

    response = await service.get_news("aapl", time_range="m")

    assert response.status == "ok"
    assert profile.calls == []
    assert runner.calls[0][0][3] == "AAPL"
    assert runner.calls[1][0][3] == "AAPL since:2026-05-03"
    assert runner.calls[2][0] == ["opencli", "xueqiu", "comments", "AAPL", "-f", "json"]


@pytest.mark.asyncio
async def test_get_news_sets_failed_sources_to_none_when_any_source_succeeds():
    runner = RecordingRunner(
        [
            OpenCliCommandResult(returncode=1, stdout="", stderr="google failed"),
            ok_result("not-json"),
            ok_result('{"comments": ["ok"]}'),
        ]
    )
    service = StockNewsService(
        profile_service=FakeProfileService(name=None),
        command_runner=runner,
        now=fixed_now,
    )

    response = await service.get_news("600519", time_range="w")

    assert response.status == "ok"
    assert response.data.google is None
    assert response.data.twitter is None
    assert response.data.xueqiu == {"comments": ["ok"]}


@pytest.mark.asyncio
async def test_get_news_raises_provider_unavailable_when_all_sources_fail():
    runner = RecordingRunner(
        [
            OpenCliCommandResult(returncode=1, stdout="", stderr="google failed"),
            ok_result("not-json"),
            OSError("opencli missing"),
        ]
    )
    service = StockNewsService(
        profile_service=FakeProfileService(name=None),
        command_runner=runner,
        now=fixed_now,
    )

    with pytest.raises(ProviderError) as raised:
        await service.get_news("600519", time_range="w")

    assert raised.value.error_type == ErrorType.PROVIDER_UNAVAILABLE
    assert raised.value.provider == "opencli"
    assert raised.value.message == "opencli did not return usable results from any stock news source."


@pytest.mark.asyncio
async def test_get_news_rejects_symbols_that_are_not_stock_codes_or_us_tickers():
    runner = RecordingRunner([])
    service = StockNewsService(profile_service=FakeProfileService(), command_runner=runner)

    with pytest.raises(ProviderError) as raised:
        await service.get_news("ABC123", time_range="w")

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert runner.calls == []
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run:

```powershell
uv run pytest tests/unit/services/test_stock_news_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.stock_news_service'`.

- [ ] **Step 3: Add the service implementation**

Create `src/services/stock_news_service.py` with this content:

```python
from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import StockNewsData, StockNewsResponse
from src.utils.symbols import NormalizedSymbol, normalize_symbol


@dataclass(frozen=True)
class OpenCliCommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class SearchTarget:
    keyword: str
    xueqiu_symbol: str


CommandRunner = Callable[[list[str], dict[str, str], float], Awaitable[OpenCliCommandResult]]
NowProvider = Callable[[], datetime]


class StockNewsService:
    def __init__(
        self,
        *,
        profile_service: Any | None = None,
        command_runner: CommandRunner | None = None,
        now: NowProvider | None = None,
        command_timeout_seconds: float = 30.0,
    ) -> None:
        self.profile_service = profile_service
        self.command_runner = command_runner or run_opencli_command
        self.now = now or (lambda: datetime.now(UTC))
        self.command_timeout_seconds = command_timeout_seconds

    async def get_news(self, symbol: str, time_range: str = "w") -> StockNewsResponse:
        target = await self._build_search_target(symbol)
        since_date = self._since_date(time_range)
        commands = {
            "google": [
                "opencli",
                "google",
                "news",
                target.keyword,
                "--lang",
                "zh",
                "--region",
                "CN",
                "-f",
                "json",
            ],
            "twitter": [
                "opencli",
                "twitter",
                "search",
                f"{target.keyword} since:{since_date}",
                "--product",
                "live",
                "--limit",
                "30",
                "-f",
                "json",
            ],
            "xueqiu": [
                "opencli",
                "xueqiu",
                "comments",
                target.xueqiu_symbol,
                "-f",
                "json",
            ],
        }
        source_names = list(commands)
        source_results = await asyncio.gather(
            *(self._source_json(commands[source]) for source in source_names)
        )
        data = dict(zip(source_names, source_results, strict=True))
        if all(value is None for value in data.values()):
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider="opencli",
                message="opencli did not return usable results from any stock news source.",
            )
        return StockNewsResponse(data=StockNewsData(**data))

    async def _build_search_target(self, raw_symbol: str) -> SearchTarget:
        value = raw_symbol.strip().upper()
        try:
            normalized = normalize_symbol(value)
        except ProviderError as exc:
            if _is_us_ticker(value):
                return SearchTarget(keyword=value, xueqiu_symbol=value)
            raise exc

        name = await self._profile_name(raw_symbol)
        keyword = normalized.display_symbol if not name else f"{normalized.display_symbol} {name}"
        return SearchTarget(
            keyword=keyword,
            xueqiu_symbol=_xueqiu_symbol(normalized),
        )

    async def _profile_name(self, raw_symbol: str) -> str | None:
        if self.profile_service is None:
            return None
        try:
            response = await self.profile_service.get_profile(raw_symbol)
        except ProviderError:
            return None
        name = getattr(getattr(response, "data", None), "name", None)
        return name or None

    async def _source_json(self, command: list[str]) -> Any | None:
        try:
            result = await self.command_runner(
                command,
                _command_env(),
                self.command_timeout_seconds,
            )
        except (OSError, TimeoutError):
            return None
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def _since_date(self, time_range: str) -> str:
        days_by_range = {"d": 1, "w": 7, "m": 30}
        days = days_by_range[time_range]
        now = self.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        else:
            now = now.astimezone(UTC)
        return (now.date() - timedelta(days=days)).isoformat()


async def run_opencli_command(
    command: list[str],
    env: dict[str, str],
    timeout_seconds: float,
) -> OpenCliCommandResult:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return OpenCliCommandResult(
        returncode=process.returncode if process.returncode is not None else 1,
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
    )


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["NODE_NO_WARNINGS"] = "1"
    return env


def _is_us_ticker(value: str) -> bool:
    return re.fullmatch(r"[A-Z]{1,10}", value) is not None


def _xueqiu_symbol(symbol: NormalizedSymbol) -> str:
    if symbol.market == "hk":
        return f"HK{symbol.symbol}"
    return f"{symbol.exchange.upper()}{symbol.symbol}"
```

- [ ] **Step 4: Run the service tests to verify they pass**

Run:

```powershell
uv run pytest tests/unit/services/test_stock_news_service.py -v
```

Expected: PASS for all service tests.

- [ ] **Step 5: Commit the service task**

Run in a Git-writable session:

```powershell
git add src/services/stock_news_service.py tests/unit/services/test_stock_news_service.py
git commit --author="Codex <codex@agenteum.com>" -m "feat: add stock news service"
```

### Task 3: MCP API And Service Wiring

**Files:**
- Modify: `src/api/mcp_full.py`
- Modify: `src/app.py`
- Modify: `src/provider_factory.py`
- Modify: `tests/unit/api/test_mcp_full.py`
- Modify: `tests/unit/test_provider_factory.py`

- [ ] **Step 1: Write the failing MCP and factory tests**

Update the existing `src.schemas` import in `tests/unit/api/test_mcp_full.py` from:

```python
from src.schemas import FallbackRecord
```

to:

```python
from src.schemas import FallbackRecord, StockNewsData, StockNewsResponse
```

Append these tests to `tests/unit/api/test_mcp_full.py`:

```python
@pytest.mark.asyncio
async def test_mcp_stock_news_tool_returns_service_response():
    class FakeNewsService:
        def __init__(self):
            self.calls = []

        async def get_news(self, symbol, time_range="w"):
            self.calls.append((symbol, time_range))
            return StockNewsResponse(
                data=StockNewsData(
                    google=[{"title": "google"}],
                    twitter=[],
                    xueqiu=[],
                )
            )

    news_service = FakeNewsService()
    mcp = create_mcp_server(news_service=news_service)

    result = _tool_result_data(
        await mcp.call_tool("stock_news", {"symbol": "600519", "time_range": "d"})
    )

    assert news_service.calls == [("600519", "d")]
    assert result == {
        "status": "ok",
        "data": {
            "google": [{"title": "google"}],
            "twitter": [],
            "xueqiu": [],
        },
    }


@pytest.mark.asyncio
async def test_mcp_stock_news_validation_errors_return_structured_error():
    mcp = create_mcp_server(news_service=object())

    result = _tool_result_data(
        await mcp.call_tool("stock_news", {"symbol": "600519", "time_range": "year"})
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_request"
    assert result["error"]["message"].startswith("Invalid parameter 'time_range'")


@pytest.mark.asyncio
async def test_mcp_stock_news_provider_errors_return_structured_error():
    class FailingNewsService:
        async def get_news(self, symbol, time_range="w"):
            raise ProviderError(
                error_type=ErrorType.PROVIDER_UNAVAILABLE,
                provider="opencli",
                message="opencli did not return usable results from any stock news source.",
            )

    mcp = create_mcp_server(news_service=FailingNewsService())

    result = _tool_result_data(await mcp.call_tool("stock_news", {"symbol": "600519"}))

    assert result["status"] == "error"
    assert result["error"]["type"] == "provider_unavailable"
    assert result["error"]["provider"] == "opencli"
    assert result["error"]["retryable"] is True
```

Update `test_mcp_server_can_be_created_with_fake_services` in `tests/unit/api/test_mcp_full.py` so the `create_mcp_server` call includes `news_service=object()`:

```python
    mcp = create_mcp_server(
        kline_service=object(),
        profile_service=object(),
        financial_service=object(),
        f10_service=object(),
        announcement_service=object(),
        research_report_service=object(),
        news_service=object(),
    )
```

Append this test to `tests/unit/test_provider_factory.py`:

```python
def test_build_services_wires_news_service_to_profile_service():
    services = build_services(
        Settings(
            AGENTEUM_FIN_A_KLINE_PROVIDER="none",
            AGENTEUM_FIN_F10_PROVIDER="none",
            AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER="none",
            AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER="none",
        )
    )

    assert services.news_service.profile_service is services.profile_service
```

- [ ] **Step 2: Run the API and factory tests to verify they fail**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py::test_mcp_stock_news_tool_returns_service_response tests/unit/api/test_mcp_full.py::test_mcp_stock_news_validation_errors_return_structured_error tests/unit/api/test_mcp_full.py::test_mcp_stock_news_provider_errors_return_structured_error tests/unit/test_provider_factory.py::test_build_services_wires_news_service_to_profile_service -v
```

Expected: FAIL because `create_mcp_server` does not accept `news_service` and `ServiceBundle` has no `news_service`.

- [ ] **Step 3: Wire the MCP tool**

In `src/api/mcp_full.py`, add `StockNewsRequest` to the schema imports:

```python
    StockNewsRequest,
```

Change the `create_mcp_server` signature to include `news_service`:

```python
def create_mcp_server(
    *,
    kline_service: Any | None = None,
    profile_service: Any | None = None,
    financial_service: Any | None = None,
    f10_service: Any | None = None,
    announcement_service: Any | None = None,
    research_report_service: Any | None = None,
    news_service: Any | None = None,
) -> FastMCP:
```

Add this MCP tool after `stock_research_reports`:

```python
    @mcp.tool()
    async def stock_news(symbol: str, time_range: str = "w") -> dict:
        """Return recent stock news and social discussion from opencli sources."""
        try:
            request = StockNewsRequest(symbol=symbol, time_range=time_range)
            response = await news_service.get_news(
                request.symbol,
                time_range=request.time_range,
            )
            return response.model_dump()
        except ProviderError as exc:
            return _provider_error_response(exc).model_dump(by_alias=True)
        except ValidationError as exc:
            return _validation_error_response(exc).model_dump(by_alias=True)
```

- [ ] **Step 4: Wire the service factory**

In `src/provider_factory.py`, import `StockNewsService`:

```python
from src.services.stock_news_service import StockNewsService
```

Add `news_service` to `ServiceBundle`:

```python
    news_service: StockNewsService
```

Replace `build_services` with this version so the same profile service instance is reused:

```python
def build_services(settings: Settings) -> ServiceBundle:
    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    retry_policy = RetryPolicy.from_settings(settings)

    kline_service = StockKlineService(
        a_share_provider=_a_kline_provider(settings.fin_a_kline_provider),
        hk_provider=_hk_kline_provider(settings.fin_hk_kline_provider),
        retry_policy=retry_policy,
    )
    profile_service = StockProfileService(
        providers=[_profile_provider(settings.fin_profile_provider, http_client)],
        retry_policy=retry_policy,
    )
    financial_service = FinancialStatementService(
        provider=_financial_provider(
            settings.fin_financial_statements_provider,
            http_client,
        ),
        retry_policy=retry_policy,
    )
    f10_service = StockF10Service(
        provider=_f10_provider(settings.fin_f10_provider),
        retry_policy=retry_policy,
    )
    announcement_service = AnnouncementService(
        provider=_announcement_provider(settings.fin_announcements_provider, http_client),
        retry_policy=retry_policy,
    )
    research_report_service = ResearchReportService(
        provider=_research_provider(settings.fin_research_reports_provider, http_client),
        retry_policy=retry_policy,
    )
    news_service = StockNewsService(profile_service=profile_service)

    return ServiceBundle(
        http_client=http_client,
        kline_service=kline_service,
        profile_service=profile_service,
        financial_service=financial_service,
        f10_service=f10_service,
        announcement_service=announcement_service,
        research_report_service=research_report_service,
        news_service=news_service,
    )
```

- [ ] **Step 5: Wire the FastAPI app**

In `src/app.py`, add the new service argument to `create_mcp_server`:

```python
    mcp = create_mcp_server(
        kline_service=services.kline_service,
        profile_service=services.profile_service,
        financial_service=services.financial_service,
        f10_service=services.f10_service,
        announcement_service=services.announcement_service,
        research_report_service=services.research_report_service,
        news_service=services.news_service,
    )
```

- [ ] **Step 6: Run the API and factory tests to verify they pass**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py::test_mcp_stock_news_tool_returns_service_response tests/unit/api/test_mcp_full.py::test_mcp_stock_news_validation_errors_return_structured_error tests/unit/api/test_mcp_full.py::test_mcp_stock_news_provider_errors_return_structured_error tests/unit/test_provider_factory.py::test_build_services_wires_news_service_to_profile_service -v
```

Expected: PASS for the new API and factory tests.

- [ ] **Step 7: Commit the wiring task**

Run in a Git-writable session:

```powershell
git add src/api/mcp_full.py src/app.py src/provider_factory.py tests/unit/api/test_mcp_full.py tests/unit/test_provider_factory.py
git commit --author="Codex <codex@agenteum.com>" -m "feat: expose stock news tool"
```

### Task 4: Resource Documentation And Full Verification

**Files:**
- Modify: `src/resources/stock-tools-guide.md`
- Modify: `src/resources/providers-capabilities.md`
- Modify: `tests/unit/api/test_mcp_full.py`

- [ ] **Step 1: Write the failing resource assertions**

Update `test_resource_markdown_files_load` in `tests/unit/api/test_mcp_full.py` to include these assertions:

```python
    assert "stock_news" in load_resource_text("stock-tools-guide.md")
    assert "opencli" in load_resource_text("providers-capabilities.md")
```

- [ ] **Step 2: Run the resource test to verify it fails**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py::test_resource_markdown_files_load -v
```

Expected: FAIL because the resource markdown does not document `stock_news` or `opencli`.

- [ ] **Step 3: Document `stock_news` in the tool guide**

Add this section to `src/resources/stock-tools-guide.md` after `stock_research_reports` and before `Fallbacks And Errors`:

```markdown
## stock_news

Purpose: recent stock news and social discussion from Google News, Twitter/X, and Xueqiu through the external `opencli` command.

Parameters: `symbol` and `time_range` (`w`, `d`, `m`). The default `time_range` is `w`.

Coverage: A-share and Hong Kong symbols use existing symbol normalization and best-effort company-name enrichment from `stock_profile`. US-style alphabetic tickers such as `AAPL` are accepted directly and skip company-name enrichment.

Limitations: this tool returns each `opencli` JSON payload as-is. It does not deduplicate, rank, translate, or summarize results. If one source fails, that source is `null`; if all three sources fail, the tool returns `provider_unavailable` for provider `opencli`.
```

- [ ] **Step 4: Document `opencli` in provider capabilities**

In `src/resources/providers-capabilities.md`, add this bullet under `Defaults`:

```markdown
- Stock news: external `opencli` command.
```

Add this bullet under `Provider Notes`:

```markdown
- opencli: external CLI used by `stock_news` for Google News, Twitter/X live search, and Xueqiu comments. Runtime environments must have `opencli` installed and available on `PATH`; commands run with `NODE_NO_WARNINGS=1` to keep stdout parseable as JSON.
```

Add this bullet under `v1 Limitations`:

```markdown
- `stock_news` depends on `opencli` and returns raw source JSON. Automated tests use fake command runners and do not call live `opencli`.
```

- [ ] **Step 5: Run the resource test to verify it passes**

Run:

```powershell
uv run pytest tests/unit/api/test_mcp_full.py::test_resource_markdown_files_load -v
```

Expected: PASS.

- [ ] **Step 6: Run focused stock news tests**

Run:

```powershell
uv run pytest tests/unit/test_schemas.py tests/unit/services/test_stock_news_service.py tests/unit/api/test_mcp_full.py tests/unit/test_provider_factory.py -v
```

Expected: PASS for all selected tests.

- [ ] **Step 7: Run full verification**

Run:

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: both commands exit with code `0`.

- [ ] **Step 8: Commit the documentation and verification task**

Run in a Git-writable session:

```powershell
git add src/resources/stock-tools-guide.md src/resources/providers-capabilities.md tests/unit/api/test_mcp_full.py
git commit --author="Codex <codex@agenteum.com>" -m "docs: document stock news tool"
```

### Task 5: Review And Final Checks

**Files:**
- Review: `docs/superpowers/specs/2026-06-02-stock-news-design.md`
- Review: `docs/superpowers/plans/2026-06-02-stock-news.md`
- Review: all files changed by Tasks 1 through 4

- [ ] **Step 1: Compare implementation against acceptance criteria**

Use this checklist:

```text
stock_news is registered on /mcp/full.
stock_news accepts symbol and time_range with default w.
time_range rejects values outside w, d, and m.
A-share and Hong Kong inputs use normalize_symbol.
US alphabetic tickers bypass normalize_symbol after it rejects them.
A-share and Hong Kong queries use profile company name when available.
Profile lookup failure does not fail stock_news.
Google command uses opencli google news [keyword] --lang zh --region CN -f json.
Twitter command uses opencli twitter search [query] --product live --limit 30 -f json.
Twitter query includes since:YYYY-MM-DD based on UTC date and time_range.
Xueqiu command uses opencli xueqiu comments [symbol] -f json.
Real command runner passes NODE_NO_WARNINGS=1.
Each source failure maps to None.
Any successful source returns status ok.
Three failed sources raise provider_unavailable for provider opencli.
Resource docs mention stock_news and opencli.
```

- [ ] **Step 2: Request code review**

Use `superpowers:requesting-code-review` after all implementation tasks pass. Review the diff from before Task 1 to the final head. Fix Critical and Important findings before final verification.

- [ ] **Step 3: Run final verification after review fixes**

Run:

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: both commands exit with code `0`.

- [ ] **Step 4: Commit review fixes**

If review produced code or test changes, run in a Git-writable session:

```powershell
git add src tests docs
git commit --author="Codex <codex@agenteum.com>" -m "fix: address stock news review findings"
```

If review produced no code or test changes, do not create an empty commit.
