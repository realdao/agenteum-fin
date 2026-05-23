from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.errors import ErrorType, ProviderError
from src.schemas import (
    FinancialStatementsData,
    FinancialStatementsRequest,
    FinancialStatementsResponse,
)
from src.services.logging import logged_provider_call
from src.services.retry import RetryPolicy, run_with_retries
from src.utils.symbols import normalize_symbol

ALL_STATEMENTS = ["balance_sheet", "income", "cash_flow"]


class FinancialStatementService:
    def __init__(self, *, provider: Any, retry_policy: RetryPolicy | None = None) -> None:
        self.provider = provider
        self.retry_policy = retry_policy or RetryPolicy()

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
        statement_types = (
            ALL_STATEMENTS if request.statement_type == "all" else [request.statement_type]
        )
        groups = [
            await logged_provider_call(
                operation=f"stock_financial_statements.{statement_type}",
                provider=self.provider.name,
                symbol=symbol,
                fallback_count=0,
                call=lambda statement_type=statement_type: run_with_retries(
                    lambda: self.provider.get_statement(
                        symbol,
                        statement_type,
                        request.periods,
                    ),
                    policy=self.retry_policy,
                ),
            )
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
