from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import StockNewsData, StockNewsResponse
from src.utils.symbols import NormalizedSymbol, normalize_symbol

LOGGER = logging.getLogger("agenteum_fin.opencli")


@dataclass(frozen=True)
class OpenCliCommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class SearchTarget:
    keyword: str
    twitter_query: str
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
        opencli = _opencli_command()
        commands = {
            "google": [
                *opencli,
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
                *opencli,
                "twitter",
                "search",
                f"{target.twitter_query}, since:{since_date}",
                "--product",
                "live",
                "--limit",
                "30",
                "-f",
                "json",
            ],
            "xueqiu": [
                *opencli,
                "xueqiu",
                "comments",
                target.xueqiu_symbol,
                "-f",
                "json",
            ],
        }
        source_names = list(commands)
        source_results = await asyncio.gather(
            *(self._source_json(source, commands[source]) for source in source_names)
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
                return SearchTarget(keyword=value, twitter_query=value, xueqiu_symbol=value)
            raise exc

        name = await self._profile_name(raw_symbol)
        keyword = normalized.display_symbol if not name else f"{normalized.display_symbol} {name}"
        return SearchTarget(
            keyword=keyword,
            twitter_query=name or normalized.display_symbol,
            xueqiu_symbol=_xueqiu_symbol(normalized),
        )

    async def _profile_name(self, raw_symbol: str) -> str | None:
        if self.profile_service is None:
            return None
        try:
            response = await self.profile_service.get_profiles([raw_symbol])
        except ProviderError:
            return None
        profiles = getattr(getattr(response, "data", None), "profiles", None) or []
        name = getattr(profiles[0], "name", None) if profiles else None
        return name or None

    async def _source_json(self, source: str, command: list[str]) -> Any | None:
        LOGGER.info(
            "opencli command start source=%s argv=%s",
            source,
            json.dumps(command, ensure_ascii=False),
        )
        try:
            result = await self.command_runner(
                command,
                _command_env(),
                self.command_timeout_seconds,
            )
        except (OSError, TimeoutError) as exc:
            LOGGER.warning(
                "opencli command exception source=%s argv=%s error=%r",
                source,
                json.dumps(command, ensure_ascii=False),
                exc,
            )
            return None
        if result.returncode != 0:
            LOGGER.warning(
                "opencli command failed source=%s returncode=%s argv=%s stderr=%s",
                source,
                result.returncode,
                json.dumps(command, ensure_ascii=False),
                _preview(result.stderr),
            )
            return None
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            LOGGER.warning(
                "opencli command invalid-json source=%s argv=%s error=%s stdout=%s",
                source,
                json.dumps(command, ensure_ascii=False),
                exc,
                _preview(result.stdout),
            )
            return None
        LOGGER.info(
            "opencli command ok source=%s argv=%s",
            source,
            json.dumps(command, ensure_ascii=False),
        )
        return payload

    def _since_date(self, time_range: str) -> str:
        days_by_range = {"d": 1, "w": 7, "m": 30}
        days = days_by_range[time_range]
        now = self.now()
        now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
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


def _preview(value: str, max_chars: int = 500) -> str:
    value = value.replace("\r", "\\r").replace("\n", "\\n")
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


def _opencli_command() -> list[str]:
    configured = os.environ.get("AGENTEUM_FIN_OPENCLI_COMMAND")
    if configured:
        return shlex.split(configured, posix=False)
    return ["opencli"]


def _is_us_ticker(value: str) -> bool:
    return re.fullmatch(r"[A-Z]{1,10}", value) is not None


def _xueqiu_symbol(symbol: NormalizedSymbol) -> str:
    if symbol.market == "hk":
        return symbol.symbol
    return f"{symbol.exchange.upper()}{symbol.symbol}"
