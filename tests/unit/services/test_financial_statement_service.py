import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import FinancialStatementGroup, FinancialStatementPeriod, FinancialStatementsRequest
from src.services.financial_statement_service import FinancialStatementService


class FakeFinancialProvider:
    name = "sina"

    async def get_statement(self, symbol, statement_type, periods):
        return FinancialStatementGroup(
            statement_type=statement_type,
            periods=[FinancialStatementPeriod(period="20260331", items=[])],
        )


@pytest.mark.asyncio
async def test_financial_service_rejects_hk_symbols():
    service = FinancialStatementService(provider=FakeFinancialProvider())

    with pytest.raises(ProviderError) as raised:
        await service.get_financial_statements(FinancialStatementsRequest(symbol="00700"))

    assert raised.value.error_type == ErrorType.UNSUPPORTED_MARKET


@pytest.mark.asyncio
async def test_financial_service_all_requests_three_statement_groups():
    service = FinancialStatementService(provider=FakeFinancialProvider())

    response = await service.get_financial_statements(FinancialStatementsRequest(symbol="600519"))

    assert [group.statement_type for group in response.data.statements] == [
        "balance_sheet",
        "income",
        "cash_flow",
    ]
