"""Live smoke test for the Iwencai (同花顺问财) flexible query layer.

Covers the 14 migrated skill capabilities end to end: 11 query domains and
3 search channels, through Settings -> provider_factory -> service -> client
-> the real Iwencai OpenAPI gateway.

Opt-in only because every case sends real queries and burns API quota:

    AGENTEUM_FIN_LIVE_SMOKE=1 uv run pytest tests/smoke/test_iwencai_live.py -v -s

Requires AGENTEUM_FIN_IWENCAI_API_KEY or IWENCAI_API_KEY (`.env` is loaded
automatically via Settings).
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from src.config import Settings
from src.provider_factory import ServiceBundle, build_services
from src.schemas import IwencaiQueryRequest, IwencaiSearchRequest

LIVE_ENABLED = os.environ.get("AGENTEUM_FIN_LIVE_SMOKE") == "1"
SETTINGS = Settings(fin_request_timeout=30.0)
API_KEY = SETTINGS.resolved_iwencai_api_key

pytestmark = pytest.mark.skipif(
    not LIVE_ENABLED or not API_KEY,
    reason=(
        "live Iwencai smoke test is opt-in: set AGENTEUM_FIN_LIVE_SMOKE=1 "
        "and configure AGENTEUM_FIN_IWENCAI_API_KEY or IWENCAI_API_KEY"
    ),
)

# One simple query per migrated hithink-* skill (aligned with the SKILL.md examples).
QUERY_CASES = {
    "finance": "同花顺营业收入",
    "market": "上证指数行情",
    "macro": "最近一期CPI",
    "industry": "A股行业估值排名",
    "business": "同花顺主营业务构成",
    "management": "前十大股东",
    "insresearch": "券商金股",
    "astock": "科技股有哪些",
    "hkstock": "港股科技股有哪些",
    "sector": "今日涨幅最大的板块有哪些",
    "index": "沪深300最新点位",
}

# One simple query per migrated *-search skill.
SEARCH_CASES = {
    "news": "人工智能",
    "report": "人工智能行业研究报告",
    "announcement": "分红派息公告",
}


async def _with_service(
    fn: Callable[[Any], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    bundle: ServiceBundle = build_services(SETTINGS)
    try:
        assert bundle.iwencai_service is not None, "iwencai_service is disabled by configuration"
        return await fn(bundle.iwencai_service)
    finally:
        await bundle.http_client.aclose()


async def _run_query(domain: str, query: str) -> dict[str, Any]:
    return await _with_service(
        lambda service: service.query(
            IwencaiQueryRequest(query=query, domain=domain, page=1, limit=5)
        )
    )


async def _run_search(channel: str, query: str) -> dict[str, Any]:
    return await _with_service(
        lambda service: service.search(IwencaiSearchRequest(query=query, channel=channel, size=5))
    )


@pytest.mark.parametrize("domain", QUERY_CASES.keys())
async def test_iwencai_query_domain_smoke(domain: str):
    envelope = await _run_query(domain, QUERY_CASES[domain])

    assert envelope["source"] == "同花顺问财"
    assert envelope["status"] == "ok", (
        f"domain={domain} gateway error: {envelope.get('error')} "
        f"gateway_response={envelope.get('gateway_response')}"
    )
    assert isinstance(envelope["datas"], list)
    assert envelope["returned_count"] == len(envelope["datas"])
    assert isinstance(envelope["code_count"], int)
    assert envelope["has_more"] == (
        envelope["code_count"] > envelope["page"] * envelope["limit"]
    )
    print(
        f"\n[query:{domain}] returned={envelope['returned_count']} "
        f"code_count={envelope['code_count']}"
    )


@pytest.mark.parametrize("channel", SEARCH_CASES.keys())
async def test_iwencai_search_channel_smoke(channel: str):
    envelope = await _run_search(channel, SEARCH_CASES[channel])

    assert envelope["source"] == "同花顺问财"
    assert envelope["status"] == "ok", (
        f"channel={channel} gateway error: {envelope.get('error')} "
        f"gateway_response={envelope.get('gateway_response')}"
    )
    assert isinstance(envelope["data"], list)
    assert envelope["returned_count"] == len(envelope["data"])
    print(f"\n[search:{channel}] returned={envelope['returned_count']}")
