import pytest
from pydantic import ValidationError

from src.schemas import (
    SNAPSHOT_SECTIONS,
    ErrorDetail,
    FallbackRecord,
    FinancialStatementsRequest,
    FundamentalSnapshotRequest,
    KlineBar,
    KlineRequest,
    KlineResponse,
    NormalizedSymbol,
    PageSizeRequest,
    ProviderStatus,
    StockProfileData,
    ToolErrorResponse,
)


def symbol():
    return NormalizedSymbol(
        market="a_share",
        exchange="sh",
        symbol="600519",
        display_symbol="600519.SH",
    )


def test_kline_request_defaults():
    request = KlineRequest(symbol="600519")

    assert request.period == "day"
    assert request.adjust == "none"
    assert request.limit is None


def test_public_request_numeric_fields_must_be_positive():
    with pytest.raises(ValidationError):
        KlineRequest(symbol="600519", limit=0)
    with pytest.raises(ValidationError):
        FinancialStatementsRequest(symbol="600519", periods=0)
    with pytest.raises(ValidationError):
        FundamentalSnapshotRequest(symbol="600519", annual_years=0)
    with pytest.raises(ValidationError):
        FundamentalSnapshotRequest(symbol="600519", annual_years=11)
    with pytest.raises(ValidationError):
        PageSizeRequest(symbol="600519", page_size=0)


def test_snapshot_request_defaults_to_all_sections():
    request = FundamentalSnapshotRequest(symbol="600519")

    assert request.sections == ["all"]
    assert request.annual_years == 5


def test_snapshot_request_rejects_unknown_sections():
    with pytest.raises(ValidationError) as raised:
        FundamentalSnapshotRequest(symbol="600519", sections=["meta", "bogus"])

    assert "bogus" in str(raised.value)


def test_snapshot_request_dedupes_sections():
    request = FundamentalSnapshotRequest(
        symbol="600519",
        sections=["meta", "meta", "growth"],
    )

    assert request.sections == ["meta", "growth"]
    assert set(SNAPSHOT_SECTIONS) == {
        "meta",
        "profile",
        "business_composition",
        "quote_valuation",
        "profitability",
        "growth",
        "operations_solvency",
        "balance_sheet_flags",
        "shareholders",
    }


def test_kline_request_rejects_compact_dates():
    with pytest.raises(ValidationError):
        KlineRequest(symbol="600519", start_date="20260522")


def test_kline_response_serializes_unified_shape():
    response = KlineResponse(
        status="ok",
        provider="mootdx",
        provider_status=ProviderStatus.OK,
        fetched_at="2026-05-22T14:58:50Z",
        fallbacks=[],
        data={
            "symbol": symbol(),
            "period": "day",
            "adjust": "none",
            "bars": [KlineBar(date="2026-05-22", open=1, high=2, low=1, close=2)],
        },
    )

    dumped = response.model_dump()

    assert dumped["status"] == "ok"
    assert dumped["data"]["bars"][0]["date"] == "2026-05-22"


def test_profile_data_allows_null_best_effort_fields():
    data = StockProfileData(
        symbol=symbol(),
        name="贵州茅台",
        price=1290.2,
        industry=None,
        listing_date=None,
        total_shares=None,
        float_shares=None,
    )

    assert data.industry is None


def test_error_response_shape():
    response = ToolErrorResponse(
        status="error",
        error=ErrorDetail(
            type="unsupported_market",
            message="Hong Kong financial statements are not supported in v1.",
            provider=None,
            retryable=False,
        ),
        fallbacks=[FallbackRecord(from_provider="a", to_provider="b", reason="timeout")],
    )

    dumped = response.model_dump()

    assert dumped["error"]["type"] == "unsupported_market"
    assert dumped["fallbacks"][0]["from_provider"] == "a"
