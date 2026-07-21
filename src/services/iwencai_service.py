from __future__ import annotations

import json
import logging
import time
from typing import Any

from src.errors import ErrorType, ProviderError, is_recoverable, redact_payload
from src.providers.iwencai.client import CallType, IwencaiRawResponse
from src.schemas import IwencaiQueryRequest, IwencaiSearchRequest
from src.services.retry import RetryPolicy, run_with_retries_indexed

SOURCE_NAME = "同花顺问财"
IWENCAI_CHAT_URL = "https://www.iwencai.com/unifiedwap/chat"

LOGGER = logging.getLogger("agenteum_fin.provider")

_QUOTA_KEYWORDS = ("额度", "quota", "次数")
_RATE_LIMIT_KEYWORDS = ("频率", "限流", "rate limit", "too many")


class IwencaiService:
    def __init__(self, *, client: Any, retry_policy: RetryPolicy | None = None) -> None:
        self.client = client
        self.retry_policy = retry_policy or RetryPolicy()

    async def query(
        self,
        request: IwencaiQueryRequest,
        *,
        call_type: CallType = "normal",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            raw = await run_with_retries_indexed(
                lambda attempt: self.client.query_data(
                    query=request.query,
                    domain=request.domain,
                    page=request.page,
                    limit=request.limit,
                    # Transport 层自动重试（attempt>=2）以 retry call-type 标记，
                    # 让网关能把同条件重发识别为重试而非新查询。
                    call_type=_attempt_call_type(call_type, attempt),
                ),
                policy=self.retry_policy,
            )
        except ProviderError as exc:
            self._log("iwencai_query", started, status="error", error_type=exc.error_type.value)
            raise
        envelope = self._query_envelope(request, raw)
        self._log_envelope("iwencai_query", started, envelope)
        return envelope

    async def search(
        self,
        request: IwencaiSearchRequest,
        *,
        call_type: CallType = "normal",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            raw = await run_with_retries_indexed(
                lambda attempt: self.client.search(
                    query=request.query,
                    channel=request.channel,
                    size=request.size,
                    call_type=_attempt_call_type(call_type, attempt),
                ),
                policy=self.retry_policy,
            )
        except ProviderError as exc:
            self._log("iwencai_search", started, status="error", error_type=exc.error_type.value)
            raise
        envelope = self._search_envelope(request, raw)
        self._log_envelope("iwencai_search", started, envelope)
        return envelope

    def _query_envelope(
        self,
        request: IwencaiQueryRequest,
        raw: IwencaiRawResponse,
    ) -> dict[str, Any]:
        base = {
            "source": SOURCE_NAME,
            "query": request.query,
            "domain": request.domain,
            "trace_id": raw.trace_id,
        }
        if raw.kind != "json_dict" or "datas" not in raw.body:
            return self._gateway_error_envelope(base, raw)
        body = raw.body
        datas = body.get("datas") or []
        # 契约脆弱点：has_more 依赖网关必返 code_count；缺失时回退 len(datas)，
        # 此时 has_more 几乎恒为 False（无法知道总量），翻页提示随之失效。
        code_count = _safe_int(body.get("code_count"), default=len(datas))
        has_more = code_count > request.page * request.limit
        envelope: dict[str, Any] = {
            "status": "ok",
            **base,
            "code_count": code_count,
            "returned_count": len(datas),
            "page": request.page,
            "limit": request.limit,
            "has_more": has_more,
            "datas": datas,
            "chunks_info": body.get("chunks_info") or {},
        }
        if has_more:
            envelope["pagination_tip"] = (
                f"共查到 {code_count} 条数据，当前返回第 {request.page} 页的 "
                f"{len(datas)} 条。如需更多数据，请使用 page 参数翻页。"
            )
        if not datas:
            envelope["empty_data_tip"] = _empty_data_tip()
        return envelope

    def _search_envelope(
        self,
        request: IwencaiSearchRequest,
        raw: IwencaiRawResponse,
    ) -> dict[str, Any]:
        base = {
            "source": SOURCE_NAME,
            "query": request.query,
            "channel": request.channel,
            "trace_id": raw.trace_id,
        }
        if raw.kind == "json_list":
            items = raw.body
            # 裸 list 响应没有可透传的外层 dict；raw_response 为合成的 {"data": [...]}
            # 包装，并非网关真实原始体，仅为与 json_dict 分支保持同一字段形状。
            gateway_body: Any = {"data": raw.body}
        elif raw.kind == "json_dict" and isinstance(raw.body.get("data"), list):
            items = raw.body["data"]
            gateway_body = raw.body
        else:
            return self._gateway_error_envelope(base, raw)
        envelope: dict[str, Any] = {
            "status": "ok",
            **base,
            "returned_count": len(items),
            "size": request.size,
            "data": items,
            # 透传体过 redact_payload：仅掩 SECRET_KEYS 命名字段，不改写数据结构。
            "raw_response": redact_payload(gateway_body),
        }
        if not items:
            envelope["empty_data_tip"] = _empty_data_tip()
        return envelope

    def _gateway_error_envelope(
        self,
        base: dict[str, Any],
        raw: IwencaiRawResponse,
    ) -> dict[str, Any]:
        error_type, message = _classify_gateway_error(raw)
        return {
            "status": "error",
            **base,
            "error": {
                "type": error_type.value,
                "message": message,
                "provider": "iwencai",
                # 限流（rate_limited）可退避后重试，故单独标 retryable；
                # 额度/次数类错误重试无意义，保持 is_recoverable 的 False。
                "retryable": is_recoverable(error_type) or error_type is ErrorType.RATE_LIMITED,
            },
            # 透传体过 redact_payload：仅掩 SECRET_KEYS 命名字段，不改写数据结构。
            "gateway_response": redact_payload(raw.body),
            # 与 ToolErrorResponse 对齐：消费端可统一读取 fallbacks 字段。
            "fallbacks": [],
        }

    def _log_envelope(self, operation: str, started: float, envelope: dict[str, Any]) -> None:
        status = envelope["status"]
        error_type = envelope["error"]["type"] if status == "error" else None
        self._log(operation, started, status=status, error_type=error_type)

    def _log(
        self,
        operation: str,
        started: float,
        *,
        status: str,
        error_type: str | None = None,
    ) -> None:
        extra = {
            "operation": operation,
            "provider": "iwencai",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "status": status,
        }
        if error_type is not None:
            extra["error_type"] = error_type
        level = logging.INFO if status == "ok" else logging.WARNING
        LOGGER.log(level, "finance provider call", extra=extra)


def _attempt_call_type(call_type: CallType, attempt: int) -> CallType:
    if call_type == "retry" or attempt >= 2:
        return "retry"
    return "normal"


def _empty_data_tip() -> str:
    return (
        "未查询到符合条件的数据。建议放宽或简化查询条件后重试，最多重试 2 次"
        "（重试时请将 is_retry 置为 true，服务端会以 retry call-type 标记；"
        "transport 层自动重试也会自动标记）。"
        f"如仍无数据，可引导用户访问同花顺问财: {IWENCAI_CHAT_URL}"
    )


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _classify_gateway_error(raw: IwencaiRawResponse) -> tuple[ErrorType, str]:
    if raw.kind != "json_dict":
        return ErrorType.INVALID_RESPONSE, "Iwencai OpenAPI returned a non-JSON or empty body."
    body = raw.body
    text = json.dumps(body, ensure_ascii=False).lower()
    message = _gateway_message(body)
    # 先判限流后判额度："请求频率超限"等限流文案含"超限"，不应被误判为额度类。
    if any(keyword in text for keyword in _RATE_LIMIT_KEYWORDS):
        return ErrorType.RATE_LIMITED, message
    if any(keyword in text for keyword in _QUOTA_KEYWORDS):
        return ErrorType.QUOTA_EXHAUSTED, message
    return ErrorType.PROVIDER_ERROR, message


def _gateway_message(body: dict[str, Any]) -> str:
    for key in ("message", "msg", "error", "error_msg", "detail"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "Iwencai OpenAPI gateway returned a business error without datas."
