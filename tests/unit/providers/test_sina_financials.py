import json
from pathlib import Path

import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.utils.symbols import normalize_symbol


@pytest.mark.asyncio
async def test_sina_maps_report_date_and_report_list_shape():
    fixture = json.loads(
        Path("tests/fixtures/sina_financial_report.json").read_text(encoding="utf-8")
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["paperCode"] == "sh600519"
        assert params["source"] == "lrb"
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SinaFinancialStatementsProvider(client=client)

    group = await provider.get_statement(normalize_symbol("600519"), "income", periods=1)

    assert group.statement_type == "income"
    assert group.periods[0].period == "20260331"
    assert group.periods[0].items[0].field_code == "f001"
    assert group.periods[0].items[0].title == "营业总收入"


@pytest.mark.asyncio
async def test_sina_rejects_unknown_statement_type_with_provider_error():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    provider = SinaFinancialStatementsProvider(client=client)

    with pytest.raises(ProviderError) as raised:
        await provider.get_statement(normalize_symbol("600519"), "unknown", periods=1)

    assert raised.value.error_type == ErrorType.INVALID_REQUEST
