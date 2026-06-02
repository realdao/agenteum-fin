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
async def test_sina_maps_nested_report_data_items_and_period_metadata():
    fixture = {
        "result": {
            "data": {
                "report_date": [
                    {"date_value": "20260331", "date_description": "2026一季报"}
                ],
                "report_list": {
                    "20260331": {
                        "rCurrency": "CNY",
                        "is_audit": "未审计",
                        "publish_date": "20260429",
                        "data": [
                            {
                                "item_field": "BIZTOTINCO",
                                "item_title": "营业总收入",
                                "item_value": "11191552278.540000",
                                "item_display_type": 1,
                                "item_group_no": 1,
                                "item_tongbi": -0.18025,
                            }
                        ],
                    }
                },
            }
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SinaFinancialStatementsProvider(client=client)

    group = await provider.get_statement(normalize_symbol("601012"), "income", periods=1)

    period = group.periods[0]
    assert period.publish_date == "20260429"
    assert period.currency == "CNY"
    assert period.audit_status == "未审计"
    assert period.items[0].field_code == "BIZTOTINCO"
    assert period.items[0].title == "营业总收入"
    assert period.items[0].value == "11191552278.540000"
    assert period.items[0].display_type == "1"
    assert period.items[0].group_number == "1"
    assert period.items[0].yoy_value == -0.18025


@pytest.mark.asyncio
async def test_sina_rejects_unknown_statement_type_with_provider_error():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    provider = SinaFinancialStatementsProvider(client=client)

    with pytest.raises(ProviderError) as raised:
        await provider.get_statement(normalize_symbol("600519"), "unknown", periods=1)

    assert raised.value.error_type == ErrorType.INVALID_REQUEST
