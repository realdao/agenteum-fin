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
