from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import (
    FinancialStatementsData,
    FinancialStatementsRequest,
    FinancialStatementsResponse,
)
from src.utils.symbols import normalize_symbol


ALL_STATEMENTS = ["balance_sheet", "income", "cash_flow"]


class FinancialStatementService:
    def __init__(self, *, provider: Any) -> None:
        self.provider = provider

    async def get_financial_statements(
        self,
        request: FinancialStatementsRequest,
    ) -> FinancialStatementsResponse:
        symbol = normalize_symbol(request.symbol)
        if symbol.market != "a_share":
            raise ProviderError(
                error_type=ErrorType.UNSUPPORTED_MARKET,
                provider=None,
                message="Hong Kong financial statements are not supported in v1.",
            )
        statement_types = ALL_STATEMENTS if request.statement_type == "all" else [request.statement_type]
        groups = [
            await self.provider.get_statement(symbol, statement_type, request.periods)
            for statement_type in statement_types
        ]
        return FinancialStatementsResponse(
            status="ok",
            provider=self.provider.name,
            provider_status="ok",
            fetched_at=datetime.now(UTC).isoformat(),
            fallbacks=[],
            data=FinancialStatementsData(symbol=symbol, statements=groups),
        )
