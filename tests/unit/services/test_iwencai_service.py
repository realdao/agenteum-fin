import json
from pathlib import Path

import pytest

from src.errors import ErrorType, ProviderError
from src.providers.iwencai.client import IwencaiRawResponse
from src.schemas import IwencaiQueryRequest, IwencaiSearchRequest
from src.services.iwencai_service import IwencaiService
from src.services.retry import RetryPolicy


def fixture_json(name: str) -> dict:
    return json.loads(Path(f"tests/fixtures/{name}").read_text(encoding="utf-8"))


class FakeIwencaiClient:
    name = "iwencai"

    def __init__(self, *, raw=None, error_type=None, failures=None):
        self.raw = raw
        self.error_type = error_type
        self.failures = failures
        self.calls = []
        self.search_calls = []

    async def query_data(self, *, query, domain, page, limit, call_type="normal"):
        self.calls.append(
            {"query": query, "domain": domain, "page": page, "limit": limit, "call_type": call_type}
        )
        self._maybe_raise()
        return self.raw

    async def search(self, *, query, channel, size, call_type="normal"):
        self.search_calls.append(
            {"query": query, "channel": channel, "size": size, "call_type": call_type}
        )
        self._maybe_raise()
        return self.raw

    def _maybe_raise(self):
        total = len(self.calls) + len(self.search_calls)
        if self.error_type and (self.failures is None or total <= self.failures):
            raise ProviderError(
                error_type=self.error_type,
                provider=self.name,
                message="iwencai failed",
            )


def raw_from_fixture(name: str) -> IwencaiRawResponse:
    return IwencaiRawResponse(kind="json_dict", body=fixture_json(name), trace_id="t" * 64)


def query_request(**overrides) -> IwencaiQueryRequest:
    params = {"query": "ROE最高的股票", "domain": "finance", "page": 1, "limit": 10}
    params.update(overrides)
    return IwencaiQueryRequest(**params)


def search_request(**overrides) -> IwencaiSearchRequest:
    params = {"query": "人工智能", "channel": "news", "size": 10}
    params.update(overrides)
    return IwencaiSearchRequest(**params)


@pytest.mark.asyncio
async def test_query_envelope_contains_all_fields():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_query_finance.json"))
    service = IwencaiService(client=client)

    envelope = await service.query(query_request(page=1, limit=10))

    assert envelope["status"] == "ok"
    assert envelope["source"] == "同花顺问财"
    assert envelope["query"] == "ROE最高的股票"
    assert envelope["domain"] == "finance"
    assert envelope["code_count"] == 25
    assert envelope["returned_count"] == 2
    assert envelope["page"] == 1
    assert envelope["limit"] == 10
    assert envelope["has_more"] is True
    assert len(envelope["datas"]) == 2
    assert envelope["chunks_info"] == {"chunk_count": 1, "chunk_index": 0}
    assert envelope["trace_id"] == "t" * 64
    assert "page 参数翻页" in envelope["pagination_tip"]
    assert "empty_data_tip" not in envelope


@pytest.mark.asyncio
async def test_query_has_more_false_on_last_page_omits_pagination_tip():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_query_finance.json"))
    service = IwencaiService(client=client)

    envelope = await service.query(query_request(page=3, limit=10))

    assert envelope["has_more"] is False
    assert "pagination_tip" not in envelope


@pytest.mark.asyncio
async def test_query_empty_datas_stays_ok_with_empty_tip():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_query_empty.json"))
    service = IwencaiService(client=client)

    envelope = await service.query(query_request())

    assert envelope["status"] == "ok"
    assert envelope["source"] == "同花顺问财"
    assert envelope["datas"] == []
    assert envelope["returned_count"] == 0
    assert envelope["has_more"] is False
    assert "最多重试 2 次" in envelope["empty_data_tip"]
    assert "https://www.iwencai.com/unifiedwap/chat" in envelope["empty_data_tip"]


@pytest.mark.asyncio
async def test_gateway_error_is_passed_through_with_source():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_gateway_error.json"))
    service = IwencaiService(client=client)

    envelope = await service.query(query_request())

    assert envelope["status"] == "error"
    assert envelope["source"] == "同花顺问财"
    assert envelope["error"]["type"] == "quota_exhausted"
    assert envelope["error"]["provider"] == "iwencai"
    assert envelope["error"]["retryable"] is False
    assert "额度不足" in envelope["error"]["message"]
    assert envelope["gateway_response"] == fixture_json("iwencai_gateway_error.json")
    assert envelope["fallbacks"] == []
    assert envelope["trace_id"] == "t" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_type", "expected_retryable"),
    [
        ("请求频率超限，请稍后再试", "rate_limited", True),
        ("当前套餐额度不足", "quota_exhausted", False),
        ("请求次数过多，已用完今日配额", "quota_exhausted", False),
        ("查询过于复杂", "provider_error", False),
    ],
)
async def test_gateway_error_keyword_classification(
    message,
    expected_type,
    expected_retryable,
):
    raw = IwencaiRawResponse(kind="json_dict", body={"message": message}, trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.query(query_request())

    assert envelope["error"]["type"] == expected_type
    assert envelope["error"]["retryable"] is expected_retryable


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["message", "msg", "error", "detail"])
async def test_gateway_message_uses_first_available_candidate_key(key):
    raw = IwencaiRawResponse(kind="json_dict", body={key: "网关业务错误"}, trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.query(query_request())

    assert envelope["error"]["message"] == "网关业务错误"


@pytest.mark.asyncio
async def test_gateway_response_is_redacted_for_secret_keys():
    body = {"message": "额度不足", "token": "abc", "detail_code": 42}
    raw = IwencaiRawResponse(kind="json_dict", body=body, trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.query(query_request())

    assert envelope["gateway_response"]["token"] == "[REDACTED]"
    assert envelope["gateway_response"]["message"] == "额度不足"
    assert envelope["gateway_response"]["detail_code"] == 42


@pytest.mark.asyncio
async def test_non_json_response_is_invalid_response_error():
    raw = IwencaiRawResponse(kind="text", body="<html>bad gateway</html>", trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.query(query_request())

    assert envelope["status"] == "error"
    assert envelope["error"]["type"] == "invalid_response"
    assert envelope["gateway_response"] == "<html>bad gateway</html>"


@pytest.mark.asyncio
async def test_service_passes_call_type_to_client():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_query_empty.json"))
    service = IwencaiService(client=client)

    await service.query(query_request(), call_type="retry")

    assert client.calls[0]["call_type"] == "retry"


@pytest.mark.asyncio
async def test_transport_retry_marks_second_attempt_as_retry():
    client = FakeIwencaiClient(
        raw=raw_from_fixture("iwencai_query_finance.json"),
        error_type=ErrorType.TIMEOUT,
        failures=1,
    )
    service = IwencaiService(
        client=client,
        retry_policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    envelope = await service.query(query_request())

    assert envelope["status"] == "ok"
    assert [call["call_type"] for call in client.calls] == ["normal", "retry"]


@pytest.mark.asyncio
async def test_search_envelope_contains_data_without_raw_response_duplicate():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_search_news.json"))
    service = IwencaiService(client=client)

    envelope = await service.search(search_request(size=10))

    assert envelope["status"] == "ok"
    assert envelope["source"] == "同花顺问财"
    assert envelope["query"] == "人工智能"
    assert envelope["channel"] == "news"
    assert envelope["size"] == 10
    assert envelope["returned_count"] == 2
    assert envelope["data"] == fixture_json("iwencai_search_news.json")["data"]
    # raw_response 曾与 data 完全重复，已移除以减半响应体积。
    assert "raw_response" not in envelope
    assert "empty_data_tip" not in envelope


@pytest.mark.asyncio
async def test_search_empty_data_adds_empty_tip():
    raw = IwencaiRawResponse(kind="json_dict", body={"data": []}, trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.search(search_request())

    assert envelope["status"] == "ok"
    assert envelope["data"] == []
    assert "empty_data_tip" in envelope


@pytest.mark.asyncio
async def test_search_list_body_is_returned_as_data():
    raw = IwencaiRawResponse(kind="json_list", body=[{"title": "x"}], trace_id="t" * 64)
    service = IwencaiService(client=FakeIwencaiClient(raw=raw))

    envelope = await service.search(search_request())

    assert envelope["status"] == "ok"
    assert envelope["returned_count"] == 1
    assert envelope["data"] == [{"title": "x"}]
    assert "raw_response" not in envelope


@pytest.mark.asyncio
async def test_search_gateway_error_passed_through():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_gateway_error.json"))
    service = IwencaiService(client=client)

    envelope = await service.search(search_request())

    assert envelope["status"] == "error"
    assert envelope["error"]["type"] == "quota_exhausted"
    assert envelope["gateway_response"]["error_code"] == "QUOTA_NOT_ENOUGH"


@pytest.mark.asyncio
async def test_timeout_is_retried_per_policy():
    client = FakeIwencaiClient(
        raw=raw_from_fixture("iwencai_query_finance.json"),
        error_type=ErrorType.TIMEOUT,
        failures=1,
    )
    service = IwencaiService(
        client=client,
        retry_policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    envelope = await service.query(query_request())

    assert envelope["status"] == "ok"
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_gateway_error_is_not_retried():
    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_gateway_error.json"))
    service = IwencaiService(
        client=client,
        retry_policy=RetryPolicy(attempts=3, backoff_seconds=0),
    )

    envelope = await service.query(query_request())

    assert envelope["status"] == "error"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_provider_error_propagates_after_retries_exhausted():
    client = FakeIwencaiClient(error_type=ErrorType.TIMEOUT)
    service = IwencaiService(
        client=client,
        retry_policy=RetryPolicy(attempts=2, backoff_seconds=0),
    )

    with pytest.raises(ProviderError) as raised:
        await service.query(query_request())

    assert raised.value.error_type == ErrorType.TIMEOUT
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_gateway_business_error_is_logged_as_error_not_ok(caplog):
    import logging

    client = FakeIwencaiClient(raw=raw_from_fixture("iwencai_gateway_error.json"))
    service = IwencaiService(client=client)

    with caplog.at_level(logging.WARNING, logger="agenteum_fin.provider"):
        await service.query(query_request())

    records = [r for r in caplog.records if r.name == "agenteum_fin.provider"]
    assert len(records) == 1
    assert records[0].status == "error"
    assert records[0].error_type == "quota_exhausted"
