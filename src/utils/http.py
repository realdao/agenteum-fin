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
