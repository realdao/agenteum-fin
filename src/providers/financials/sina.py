from __future__ import annotations

import httpx

from src.errors import ErrorType, ProviderError
from src.schemas import FinancialLineItem, FinancialStatementGroup, FinancialStatementPeriod
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol

SINA_SOURCE_BY_STATEMENT = {
    "income": "lrb",
    "balance_sheet": "fzb",
    "cash_flow": "llb",
}


class SinaFinancialStatementsProvider:
    name = "sina"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_statement(
        self,
        symbol: NormalizedSymbol,
        statement_type: str,
        periods: int,
    ) -> FinancialStatementGroup:
        if statement_type not in SINA_SOURCE_BY_STATEMENT:
            raise ProviderError(
                error_type=ErrorType.INVALID_REQUEST,
                provider=self.name,
                message=f"Unsupported Sina statement type: {statement_type}",
            )
        source = SINA_SOURCE_BY_STATEMENT[statement_type]
        prefix = "sh" if symbol.exchange == "sh" else "sz"
        payload = await get_json(
            self.client,
            self.url,
            provider=self.name,
            params={
                "paperCode": f"{prefix}{symbol.symbol}",
                "source": source,
                "type": "0",
                "page": "1",
                "num": str(periods),
            },
        )
        data = ((payload.get("result") or {}).get("data") or {})
        report_dates = data.get("report_date") or []
        report_list = data.get("report_list") or {}
        mapped_periods: list[FinancialStatementPeriod] = []
        for report_date in report_dates[:periods]:
            period = report_date.get("date_value")
            raw_period = report_list.get(period) or {}
            mapped_periods.append(
                FinancialStatementPeriod(
                    period=str(period),
                    description=report_date.get("date_description"),
                    publish_date=_period_value(raw_period, "publish_date"),
                    currency=_period_value(raw_period, "rCurrency"),
                    audit_status=_period_value(raw_period, "is_audit"),
                    items=_map_line_items(raw_period, statement_type),
                )
            )
        return FinancialStatementGroup(statement_type=statement_type, periods=mapped_periods)


def _map_line_items(raw_period: object, statement_type: str) -> list[FinancialLineItem]:
    if not isinstance(raw_period, dict):
        return []
    if isinstance(raw_period.get("data"), list):
        return [
            _map_nested_line_item(item, statement_type)
            for item in raw_period["data"]
            if isinstance(item, dict)
        ]
    return [
        _map_legacy_line_item(field_code, item, statement_type)
        for field_code, item in raw_period.items()
        if isinstance(item, dict)
    ]


def _map_nested_line_item(item: dict[str, object], statement_type: str) -> FinancialLineItem:
    field_code = str(item.get("item_field") or "")
    return FinancialLineItem(
        field_code=field_code,
        title=str(item.get("item_title") or field_code),
        value=item.get("item_value"),
        display_type=_string_or_none(item.get("item_display_type")),
        group_number=_string_or_none(item.get("item_group_no")),
        source_statement_type=statement_type,
        yoy_value=item.get("item_tongbi"),
    )


def _map_legacy_line_item(
    field_code: str,
    item: dict[str, object],
    statement_type: str,
) -> FinancialLineItem:
    return FinancialLineItem(
        field_code=str(field_code),
        title=str(item.get("item_title") or field_code),
        value=item.get("value"),
        display_type=_string_or_none(item.get("display_type")),
        group_number=_string_or_none(item.get("group_num")),
        source_statement_type=statement_type,
        yoy_value=item.get("yoy"),
    )


def _period_value(raw_period: object, key: str) -> str | None:
    if not isinstance(raw_period, dict):
        return None
    return _string_or_none(raw_period.get(key))


def _string_or_none(value: object) -> str | None:
    return None if value is None else str(value)
