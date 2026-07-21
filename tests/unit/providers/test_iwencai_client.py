import json
import re
from pathlib import Path

import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.iwencai.client import (
    CHANNEL_SKILL_IDS,
    DOMAIN_SKILL_IDS,
    QUERY_URL,
    SEARCH_URL,
    IwencaiClient,
)

EXPECTED_CLAW_HEADERS = {
    "X-Claw-Call-Type",
    "X-Claw-Skill-Id",
    "X-Claw-Skill-Version",
    "X-Claw-Plugin-Id",
    "X-Claw-Plugin-Version",
    "X-Claw-Trace-Id",
}


def fixture_json(name: str) -> dict:
    return json.loads(Path(f"tests/fixtures/{name}").read_text(encoding="utf-8"))


def make_client(handler, *, api_key="test-key") -> IwencaiClient:
    return IwencaiClient(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        api_key=api_key,
    )


@pytest.mark.asyncio
async def test_query_data_builds_full_claw_headers_and_string_page_limit():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=fixture_json("iwencai_query_finance.json"))

    client = make_client(handler)
    raw = await client.query_data(query="ROE最高的股票", domain="finance", page=2, limit=20)

    assert captured["url"] == QUERY_URL
    headers = captured["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"
    assert {h.lower() for h in EXPECTED_CLAW_HEADERS} <= set(headers.keys())
    assert headers["X-Claw-Call-Type"] == "normal"
    assert headers["X-Claw-Skill-Id"] == "hithink-finance-query"
    assert headers["X-Claw-Skill-Version"] == "1.0.0"
    assert headers["X-Claw-Plugin-Id"] == "none"
    assert headers["X-Claw-Plugin-Version"] == "none"
    assert re.fullmatch(r"[0-9a-f]{64}", headers["X-Claw-Trace-Id"])

    assert captured["payload"] == {
        "query": "ROE最高的股票",
        "page": "2",
        "limit": "20",
        "is_cache": "1",
        "expand_index": "true",
    }

    assert raw.kind == "json_dict"
    assert raw.body["code_count"] == 25
    assert re.fullmatch(r"[0-9a-f]{64}", raw.trace_id)


@pytest.mark.asyncio
async def test_query_data_generates_fresh_trace_id_per_request():
    trace_ids = []

    async def handler(request: httpx.Request) -> httpx.Response:
        trace_ids.append(request.headers["X-Claw-Trace-Id"])
        return httpx.Response(200, json={"datas": []})

    client = make_client(handler)
    await client.query_data(query="a", domain="macro", page=1, limit=10)
    await client.query_data(query="b", domain="macro", page=1, limit=10)

    assert len(set(trace_ids)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "skill_id"),
    sorted(DOMAIN_SKILL_IDS.items()),
)
async def test_domain_to_skill_id_mapping(domain, skill_id):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Claw-Skill-Id"] == skill_id
        return httpx.Response(200, json={"datas": []})

    client = make_client(handler)
    await client.query_data(query="q", domain=domain, page=1, limit=10)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel", "skill_id", "version"),
    [
        ("news", "news-search", "1.0.0"),
        ("report", "report-search", "2.0.0"),
        ("announcement", "announcement-search", "1.0.0"),
    ],
)
async def test_search_channel_mapping_and_payload(channel, skill_id, version):
    assert CHANNEL_SKILL_IDS[channel] == skill_id
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=fixture_json("iwencai_search_news.json"))

    client = make_client(handler)
    raw = await client.search(query="人工智能", channel=channel, size=5, call_type="retry")

    assert captured["url"] == SEARCH_URL
    headers = captured["headers"]
    assert headers["X-Claw-Skill-Id"] == skill_id
    assert headers["X-Claw-Skill-Version"] == version
    assert headers["X-Claw-Call-Type"] == "retry"
    assert captured["payload"] == {
        "query": "人工智能",
        "channels": [channel],
        "app_id": "AIME_SKILL",
        "size": 5,
    }
    assert raw.kind == "json_dict"


@pytest.mark.asyncio
async def test_missing_api_key_raises_config_error_with_guidance():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not be sent without an API key")

    client = make_client(handler, api_key=None)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.CONFIG_ERROR
    assert raised.value.provider == "iwencai"
    assert "iwencai.com/skillhub" in raised.value.message


@pytest.mark.asyncio
async def test_timeout_maps_to_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.TIMEOUT
    assert raised.value.provider == "iwencai"


@pytest.mark.asyncio
async def test_network_error_maps_to_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.NETWORK


@pytest.mark.asyncio
async def test_http_5xx_maps_to_provider_5xx():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.PROVIDER_5XX
    assert raised.value.http_status == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_http_auth_errors_map_to_auth_error(status):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "invalid key"})

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.AUTH_ERROR
    assert raised.value.http_status == status


@pytest.mark.asyncio
async def test_http_4xx_maps_to_invalid_request():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "bad request"})

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raised.value.error_type == ErrorType.INVALID_REQUEST


@pytest.mark.asyncio
async def test_gateway_business_error_is_returned_not_raised():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture_json("iwencai_gateway_error.json"))

    client = make_client(handler)
    raw = await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raw.kind == "json_dict"
    assert "datas" not in raw.body
    assert raw.body["error_code"] == "QUOTA_NOT_ENOUGH"


@pytest.mark.asyncio
async def test_empty_body_parses_as_text_kind():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    client = make_client(handler)
    raw = await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raw.kind == "text"
    assert raw.body == ""


@pytest.mark.asyncio
async def test_non_json_body_parses_as_text_kind():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>bad gateway</html>")

    client = make_client(handler)
    raw = await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert raw.kind == "text"
    assert "bad gateway" in raw.body


@pytest.mark.asyncio
async def test_list_body_parses_as_json_list_kind():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"title": "x"}])

    client = make_client(handler)
    raw = await client.search(query="q", channel="news", size=10)

    assert raw.kind == "json_list"
    assert raw.body == [{"title": "x"}]


@pytest.mark.asyncio
async def test_error_payload_masks_api_key_echoed_in_body():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error, echoed Authorization: Bearer test-key")

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="finance", page=1, limit=10)

    assert "test-key" not in raised.value.payload
    assert "[REDACTED]" in raised.value.payload


@pytest.mark.asyncio
async def test_unknown_domain_raises_invalid_request_not_key_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not be sent for an unknown domain")

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.query_data(query="q", domain="crypto", page=1, limit=10)

    assert raised.value.error_type == ErrorType.INVALID_REQUEST
    assert raised.value.provider == "iwencai"


@pytest.mark.asyncio
async def test_unknown_channel_raises_invalid_request_not_key_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not be sent for an unknown channel")

    client = make_client(handler)

    with pytest.raises(ProviderError) as raised:
        await client.search(query="q", channel="weibo", size=10)

    assert raised.value.error_type == ErrorType.INVALID_REQUEST
    assert raised.value.provider == "iwencai"
