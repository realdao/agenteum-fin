from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from src.errors import ErrorType, ProviderError, redact_payload

QUERY_URL = "https://openapi.iwencai.com/v1/query2data"
SEARCH_URL = "https://openapi.iwencai.com/v1/comprehensive/search"

DEFAULT_SKILL_VERSION = "1.0.0"

DOMAIN_SKILL_IDS = {
    "finance": "hithink-finance-query",
    "market": "hithink-market-query",
    "macro": "hithink-macro-query",
    "industry": "hithink-industry-query",
    "business": "hithink-business-query",
    "management": "hithink-management-query",
    "insresearch": "hithink-insresearch-query",
    "astock": "hithink-astock-selector",
    "hkstock": "hithink-hkstock-selector",
    "sector": "hithink-sector-selector",
    "index": "hithink-zhishu-query",
}

CHANNEL_SKILL_IDS = {
    "news": "news-search",
    "report": "report-search",
    "announcement": "announcement-search",
}

SKILL_VERSIONS = {
    "report-search": "2.0.0",
}

MISSING_API_KEY_MESSAGE = (
    "IWENCAI_API_KEY is not configured. "
    "获取指引：打开 https://www.iwencai.com/skillhub 登录 → 点击 Skill → "
    "安装方式-Agent用户 → 复制您的 IWENCAI_API_KEY，"
    "然后设置环境变量 AGENTEUM_FIN_IWENCAI_API_KEY 或 IWENCAI_API_KEY。"
)

CallType = Literal["normal", "retry"]


@dataclass(frozen=True)
class IwencaiRawResponse:
    """HTTP 200 响应的容错解析结果，保持网关原始 payload 不改写。"""

    kind: Literal["json_dict", "json_list", "text"]
    body: Any
    trace_id: str


class IwencaiClient:
    name = "iwencai"

    def __init__(self, *, client: httpx.AsyncClient, api_key: str | None) -> None:
        self.client = client
        self.api_key = api_key

    async def query_data(
        self,
        *,
        query: str,
        domain: str,
        page: int,
        limit: int,
        call_type: CallType = "normal",
    ) -> IwencaiRawResponse:
        self._require_api_key()
        skill_id = self._skill_id(DOMAIN_SKILL_IDS, domain, kind="domain")
        trace_id = secrets.token_hex(32)
        payload = {
            "query": query,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true",
        }
        headers = self._headers(skill_id=skill_id, call_type=call_type, trace_id=trace_id)
        response = await self._post(QUERY_URL, payload=payload, headers=headers)
        return _parse_response_body(response, trace_id)

    async def search(
        self,
        *,
        query: str,
        channel: str,
        size: int,
        call_type: CallType = "normal",
    ) -> IwencaiRawResponse:
        self._require_api_key()
        skill_id = self._skill_id(CHANNEL_SKILL_IDS, channel, kind="channel")
        trace_id = secrets.token_hex(32)
        payload = {
            "query": query,
            "channels": [channel],
            "app_id": "AIME_SKILL",
            # 有意的不对称：search 端点的 size 按 int 发送，而 query 端点的
            # page/limit 按 str 发送——两端点契约不同，live 已分别验证。
            "size": size,
        }
        headers = self._headers(skill_id=skill_id, call_type=call_type, trace_id=trace_id)
        response = await self._post(SEARCH_URL, payload=payload, headers=headers)
        return _parse_response_body(response, trace_id)

    def _skill_id(self, mapping: dict[str, str], value: str, *, kind: str) -> str:
        skill_id = mapping.get(value)
        if skill_id is None:
            raise ProviderError(
                error_type=ErrorType.INVALID_REQUEST,
                provider=self.name,
                message=f"Unsupported iwencai {kind}: {value}",
            )
        return skill_id

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise ProviderError(
                error_type=ErrorType.CONFIG_ERROR,
                provider=self.name,
                message=MISSING_API_KEY_MESSAGE,
            )

    def _headers(self, *, skill_id: str, call_type: CallType, trace_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Id": skill_id,
            "X-Claw-Skill-Version": SKILL_VERSIONS.get(skill_id, DEFAULT_SKILL_VERSION),
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": trace_id,
        }

    async def _post(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        try:
            response = await self.client.post(url, json=payload, headers=headers)
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
        if response.status_code >= 500:
            raise ProviderError(
                error_type=ErrorType.PROVIDER_5XX,
                provider=self.name,
                message=f"Iwencai OpenAPI returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=redact_payload(self._mask_api_key(response.text)),
            )
        if response.status_code in (401, 403):
            raise ProviderError(
                error_type=ErrorType.AUTH_ERROR,
                provider=self.name,
                message=f"Iwencai OpenAPI returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=redact_payload(self._mask_api_key(response.text)),
            )
        if response.status_code >= 400:
            raise ProviderError(
                error_type=ErrorType.INVALID_REQUEST,
                provider=self.name,
                message=f"Iwencai OpenAPI returned HTTP {response.status_code}.",
                http_status=response.status_code,
                payload=redact_payload(self._mask_api_key(response.text)),
            )
        return response

    def _mask_api_key(self, text: str) -> str:
        # redact_payload 对字符串仅截断不脱敏；若错误响应体回显了 Bearer key，
        # 先按值掩码再截断，避免 key 泄漏进日志/异常 payload。
        if self.api_key:
            return text.replace(self.api_key, "[REDACTED]")
        return text


def _parse_response_body(response: httpx.Response, trace_id: str) -> IwencaiRawResponse:
    text = response.text
    if not text.strip():
        return IwencaiRawResponse(kind="text", body="", trace_id=trace_id)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return IwencaiRawResponse(kind="text", body=text, trace_id=trace_id)
    if isinstance(parsed, dict):
        return IwencaiRawResponse(kind="json_dict", body=parsed, trace_id=trace_id)
    if isinstance(parsed, list):
        return IwencaiRawResponse(kind="json_list", body=parsed, trace_id=trace_id)
    return IwencaiRawResponse(kind="text", body=str(parsed), trace_id=trace_id)
