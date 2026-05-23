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
            raw_items = report_list.get(period) or {}
            mapped_periods.append(
                FinancialStatementPeriod(
                    period=str(period),
                    description=report_date.get("date_description"),
                    items=[
                        FinancialLineItem(
                            field_code=str(field_code),
                            title=str(item.get("item_title") or field_code),
                            value=item.get("value"),
                            display_type=item.get("display_type"),
                            group_number=item.get("group_num"),
                            source_statement_type=statement_type,
                            yoy_value=item.get("yoy"),
                        )
                        for field_code, item in raw_items.items()
                        if isinstance(item, dict)
                    ],
                )
            )
        return FinancialStatementGroup(statement_type=statement_type, periods=mapped_periods)
