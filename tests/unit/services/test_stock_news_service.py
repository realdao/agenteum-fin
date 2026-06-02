from __future__ import annotations

import logging
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
        "贵州茅台, since:2026-05-26",
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
    assert runner.calls[1][0][3] == "00700.HK, since:2026-06-01"
    assert runner.calls[2][0] == ["opencli", "xueqiu", "comments", "00700", "-f", "json"]


@pytest.mark.asyncio
async def test_get_news_uses_company_name_only_for_enriched_hk_twitter_query():
    runner = RecordingRunner(
        [
            ok_result("[]"),
            ok_result("[]"),
            ok_result("[]"),
        ]
    )
    profile = FakeProfileService(name="快手-W")
    service = StockNewsService(profile_service=profile, command_runner=runner, now=fixed_now)

    response = await service.get_news("01024", time_range="w")

    assert response.status == "ok"
    assert profile.calls == ["01024"]
    assert runner.calls[0][0][3] == "01024.HK 快手-W"
    assert runner.calls[1][0][3] == "快手-W, since:2026-05-26"
    assert runner.calls[2][0] == ["opencli", "xueqiu", "comments", "01024", "-f", "json"]


@pytest.mark.asyncio
async def test_get_news_logs_opencli_command_arguments_and_failures(caplog):
    runner = RecordingRunner(
        [
            ok_result("[]"),
            OpenCliCommandResult(returncode=1, stdout="", stderr="twitter failed"),
            ok_result("[]"),
        ]
    )
    service = StockNewsService(
        profile_service=FakeProfileService(name="快手-W"),
        command_runner=runner,
        now=fixed_now,
    )

    with caplog.at_level(logging.INFO, logger="agenteum_fin.opencli"):
        response = await service.get_news("01024", time_range="w")

    assert response.status == "ok"
    assert response.data.twitter is None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        (
            'opencli command start source=twitter argv=["opencli", "twitter", '
            '"search", "快手-W, since:2026-05-26"'
        )
        in message
        for message in messages
    )
    assert any(
        "opencli command failed source=twitter returncode=1" in message
        and "twitter failed" in message
        for message in messages
    )


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
    assert runner.calls[1][0][3] == "AAPL, since:2026-05-03"
    assert runner.calls[2][0] == ["opencli", "xueqiu", "comments", "AAPL", "-f", "json"]


@pytest.mark.asyncio
async def test_get_news_allows_opencli_command_override_from_environment(monkeypatch):
    monkeypatch.setenv("AGENTEUM_FIN_OPENCLI_COMMAND", "python fake_opencli.py")
    runner = RecordingRunner(
        [
            ok_result("[]"),
            ok_result("[]"),
            ok_result("[]"),
        ]
    )
    service = StockNewsService(
        profile_service=FakeProfileService(name=None),
        command_runner=runner,
        now=fixed_now,
    )

    response = await service.get_news("AAPL", time_range="w")

    assert response.status == "ok"
    assert runner.calls[0][0][:4] == ["python", "fake_opencli.py", "google", "news"]
    assert runner.calls[1][0][:4] == ["python", "fake_opencli.py", "twitter", "search"]
    assert runner.calls[2][0][:5] == ["python", "fake_opencli.py", "xueqiu", "comments", "AAPL"]


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
    assert (
        raised.value.message
        == "opencli did not return usable results from any stock news source."
    )


@pytest.mark.asyncio
async def test_get_news_rejects_symbols_that_are_not_stock_codes_or_us_tickers():
    runner = RecordingRunner([])
    service = StockNewsService(profile_service=FakeProfileService(), command_runner=runner)

    with pytest.raises(ProviderError) as raised:
        await service.get_news("ABC123", time_range="w")

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
    assert runner.calls == []
