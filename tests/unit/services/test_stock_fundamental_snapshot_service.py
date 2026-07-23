import pytest

from src.errors import ErrorType, ProviderError
from src.providers.fundamental.eastmoney import CapitalStructure, CompanySurvey
from src.schemas import (
    BusinessComposition,
    BusinessCompositionItem,
    FundamentalSnapshotRequest,
    ShareholderItem,
    Shareholders,
    StockProfileData,
)
from src.services.stock_fundamental_snapshot_service import (
    StockFundamentalSnapshotService,
)
from src.utils.symbols import normalize_symbol

SYMBOL = normalize_symbol("600519")

ABSTRACT = {
    "营业总收入": {"20260331": 500e8, "20251231": 1700e8, "20250331": 480e8, "20241231": 1600e8},
    "归母净利润": {"20260331": 260e8, "20251231": 800e8, "20250331": 250e8, "20241231": 750e8},
    "扣非净利润": {"20260331": 259e8, "20251231": 790e8, "20250331": 248e8, "20241231": 740e8},
    "股东权益合计(净资产)": {"20251231": 2500e8, "20241231": 2200e8},
    "经营现金流量净额": {"20251231": 600e8, "20241231": 550e8},
}

BS_ROWS = [
    {
        "报告日": "20260331",
        "资产总计": 3100e8,
        "负债合计": 520e8,
        "流动资产合计": 2050e8,
        "流动负债合计": 410e8,
        "货币资金": 520e8,
        "应收账款": 1.2e8,
        "存货": 610e8,
        "短期借款": 10e8,
        "长期借款": 20e8,
        "一年内到期的非流动负债": 5e8,
    },
    {
        "报告日": "20251231",
        "资产总计": 3000e8,
        "负债合计": 500e8,
        "流动资产合计": 2000e8,
        "流动负债合计": 400e8,
        "货币资金": 500e8,
        "应收账款": 1e8,
        "存货": 600e8,
        "短期借款": 10e8,
        "长期借款": 20e8,
        "一年内到期的非流动负债": 5e8,
        "长期股权投资": 2e8,
    },
    {
        "报告日": "20241231",
        "资产总计": 2800e8,
        "负债合计": 480e8,
        "流动资产合计": 1800e8,
        "流动负债合计": 380e8,
        "货币资金": 450e8,
        "应收账款": 0.9e8,
        "存货": 550e8,
        "短期借款": 8e8,
        "长期借款": 18e8,
        "一年内到期的非流动负债": 4e8,
    },
]

INC_ROWS = [
    {
        "报告日": "20251231",
        "营业收入": 1690e8,
        "营业成本": 150e8,
        "投资收益": 0.5e8,
        "公允价值变动收益": 0.8e8,
    },
    {
        "报告日": "20241231",
        "营业收入": 1590e8,
        "营业成本": 160e8,
        "投资收益": 0.3e8,
        "公允价值变动收益": 0.2e8,
    },
]


class _FakeProvider:
    """method_name -> 返回值或 ProviderError；记录方法调用用于断言按需取数。"""

    def __init__(self, name: str, results: dict):
        self.name = name
        self._results = results
        self.calls: list[str] = []

    def __getattr__(self, item: str):
        if item not in self._results:
            raise AttributeError(item)
        result = self._results[item]

        async def method(*args):
            self.calls.append(item)
            if isinstance(result, Exception):
                raise result
            return result

        return method


def _survey() -> CompanySurvey:
    return CompanySurvey(
        name="贵州茅台",
        full_name="贵州茅台酒股份有限公司",
        industry_sw="食品饮料-饮料-白酒",
        industry_csrc="制造业-酒、饮料和精制茶制造业",
        chairman="陈华",
        introduction="茅台公司简介。",
        business_scope="茅台酒及系列酒的生产与销售。",
        founded_date="1999-11-20",
        listing_date="2001-08-27",
        employees=34992,
    )


def _holders() -> Shareholders:
    return Shareholders(
        holder_count=243159,
        holder_count_date="2026-03-31",
        holder_count_change_pct=-4.98,
        controller="贵州省国资委",
        top10_date="2026-03-31",
        top10=[
            ShareholderItem(rank=1, name="茅台集团", shares=681282935, ratio_pct=54.4),
        ],
    )


def _composition() -> BusinessComposition:
    return BusinessComposition(
        period="2025-12-31",
        by_industry=[
            BusinessCompositionItem(
                name="酒类",
                revenue_yi=1687.7459,
                cost_yi=148.059,
                gross_margin_pct=91.23,
                revenue_pct=99.96,
            )
        ],
        by_product=[
            BusinessCompositionItem(
                name="茅台酒",
                revenue_yi=1464.9991,
                gross_margin_pct=93.53,
                revenue_pct=86.77,
            )
        ],
    )


def _quote() -> StockProfileData:
    return StockProfileData(
        symbol=SYMBOL,
        name="贵州茅台",
        price=1292.01,
        market_cap=16151.2e8,
        float_market_cap=16151.2e8,
        pe_ttm=19.53,
        pe_static=14.82,
        pb=6.94,
        currency="CNY",
    )


def _service(**overrides) -> StockFundamentalSnapshotService:
    providers = {
        "profile_provider": _FakeProvider(
            "eastmoney",
            {
                "get_company_survey": _survey(),
                "get_shareholders": _holders(),
                "get_capital_structure": CapitalStructure(
                    total_shares=1250081601,
                    limited_shares=0,
                    float_shares=1250081601,
                ),
                "get_business_composition": _composition(),
            },
        ),
        "financials_provider": _FakeProvider(
            "akshare",
            {
                "get_financial_abstract": ABSTRACT,
                "get_balance_sheet": BS_ROWS,
                "get_income_statement": INC_ROWS,
            },
        ),
        "quote_provider": _FakeProvider("tencent", {"get_profiles": [_quote()]}),
    }
    providers.update(overrides)
    return StockFundamentalSnapshotService(**providers)


@pytest.mark.asyncio
async def test_full_snapshot_covers_all_blocks():
    response = await _service().get_snapshot(FundamentalSnapshotRequest(symbol="600519.SH"))
    data = response.data

    assert response.status == "ok"
    assert response.provider == "multi"
    assert data.meta.name == "贵州茅台"
    assert data.meta.market == "a_share"
    assert data.meta.exchange == "sh"
    assert data.meta.currency == "CNY"
    assert data.meta.total_shares == 1250081601
    assert data.profile.controller == "贵州省国资委"
    assert data.profile.business_scope == "茅台酒及系列酒的生产与销售。"
    assert data.business_composition.period == "2025-12-31"
    assert data.business_composition.by_product[0].name == "茅台酒"

    valuation = data.quote_valuation
    assert valuation.price == 1292.01
    assert valuation.market_cap_yi == 16151.2
    assert valuation.pe_ttm == 19.53
    assert valuation.ttm_net_profit_yi == 810
    assert valuation.pe_ttm_calculated == pytest.approx(19.94, abs=0.01)
    assert valuation.pe_ttm_deducted == pytest.approx(20.16, abs=0.01)
    assert valuation.ps_ttm == pytest.approx(9.39, abs=0.01)

    annual = data.profitability.annual[0]
    assert annual.period == "20251231"
    assert annual.deducted_net_profit_yi == 790
    assert annual.roe_pct == pytest.approx(32.0, abs=0.01)
    assert data.profitability.latest_quarter.period == "20260331"
    assert data.profitability.latest_quarter.revenue_yi == 500

    assert data.growth[0].deducted_net_profit_yoy_pct == pytest.approx(6.76, abs=0.01)

    ops = data.operations_solvency[0]
    assert ops.period == "20260331"
    assert ops.liability_ratio_pct == pytest.approx(16.77, abs=0.01)
    annual_ops = next(row for row in data.operations_solvency if row.period == "20251231")
    assert annual_ops.interest_bearing_debt_yi == 35

    assert data.balance_sheet_flags.investment_income_yi == 0.5
    assert data.balance_sheet_flags.fair_value_gain_to_net_profit == pytest.approx(
        0.001, abs=0.0001
    )
    assert data.shareholders.holder_count == 243159
    assert data.shareholders.top10[0].name == "茅台集团"

    # 所有 block 都有成功来源标注；missing 只剩静态能力缺口
    assert set(data.providers) == {
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
    assert data.providers["quote_valuation"] == ["akshare", "tencent"]
    assert {item.item for item in data.missing} == {
        "customer_concentration",
        "volume_price_split",
        "market_size_and_cagr",
        "peer_comparison",
        "industry_chain_position",
    }
    assert data.notes


@pytest.mark.asyncio
async def test_eastmoney_failure_degrades_only_eastmoney_blocks():
    failing = _FakeProvider(
        "eastmoney",
        {
            method: ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="eastmoney",
                message="timed out",
            )
            for method in (
                "get_company_survey",
                "get_shareholders",
                "get_capital_structure",
                "get_business_composition",
            )
        },
    )
    response = await _service(profile_provider=failing).get_snapshot(
        FundamentalSnapshotRequest(symbol="600519")
    )
    data = response.data

    for block in ("meta", "profile", "business_composition", "shareholders"):
        assert getattr(data, block) is None
    missing = {item.item: item for item in data.missing}
    for block in ("meta", "profile", "business_composition", "shareholders"):
        assert block in missing
        assert missing[block].reason.startswith("timeout")

    assert data.quote_valuation.pe_ttm_calculated is not None
    assert data.profitability.annual
    assert data.growth
    assert data.operations_solvency
    assert data.balance_sheet_flags is not None


@pytest.mark.asyncio
async def test_akshare_failure_degrades_financial_blocks_but_keeps_quote():
    failing = _FakeProvider(
        "akshare",
        {
            method: ProviderError(
                error_type=ErrorType.NETWORK,
                provider="akshare",
                message="connection reset",
            )
            for method in (
                "get_financial_abstract",
                "get_balance_sheet",
                "get_income_statement",
            )
        },
    )
    response = await _service(financials_provider=failing).get_snapshot(
        FundamentalSnapshotRequest(symbol="600519")
    )
    data = response.data

    for block in ("profitability", "growth", "operations_solvency", "balance_sheet_flags"):
        assert getattr(data, block) is None
    missing = {item.item: item for item in data.missing}
    for block in ("profitability", "growth", "operations_solvency", "balance_sheet_flags"):
        assert block in missing
        assert missing[block].reason.startswith("network")

    # quote_valuation 保留行情字段，TTM 衍生字段随 abstract 缺失而为 null
    assert data.quote_valuation.price == 1292.01
    assert data.quote_valuation.pe_ttm_calculated is None
    assert data.meta.name == "贵州茅台"
    assert data.shareholders.holder_count == 243159


@pytest.mark.asyncio
async def test_quote_failure_degrades_only_valuation_block():
    failing = _FakeProvider(
        "tencent",
        {
            "get_profiles": ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider="tencent",
                message="timed out",
            )
        },
    )
    response = await _service(quote_provider=failing).get_snapshot(
        FundamentalSnapshotRequest(symbol="600519")
    )
    data = response.data

    assert data.quote_valuation is None
    assert "quote_valuation" in {item.item for item in data.missing}
    assert data.profitability.annual
    assert data.meta.name == "贵州茅台"


@pytest.mark.asyncio
async def test_unconfigured_providers_degrade_all_blocks():
    service = StockFundamentalSnapshotService(
        profile_provider=None,
        financials_provider=None,
        quote_provider=None,
    )
    response = await service.get_snapshot(FundamentalSnapshotRequest(symbol="600519"))
    data = response.data

    failed = {item.item: item for item in data.missing if item.hint is None}
    assert set(failed) == {
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
    assert all("provider_unavailable" in item.reason for item in failed.values())


@pytest.mark.asyncio
async def test_hk_symbol_returns_degraded_snapshot_without_calling_providers():
    profile_provider = _FakeProvider("eastmoney", {})
    financials_provider = _FakeProvider("akshare", {})
    quote_provider = _FakeProvider("tencent", {})
    service = StockFundamentalSnapshotService(
        profile_provider=profile_provider,
        financials_provider=financials_provider,
        quote_provider=quote_provider,
    )

    response = await service.get_snapshot(FundamentalSnapshotRequest(symbol="00700.HK"))
    data = response.data

    assert response.status == "ok"
    for block in (
        "meta",
        "profile",
        "business_composition",
        "quote_valuation",
        "profitability",
        "growth",
        "operations_solvency",
        "balance_sheet_flags",
        "shareholders",
    ):
        assert getattr(data, block) is None
    assert len(data.missing) == 9
    assert all("unsupported_market" in item.reason for item in data.missing)
    assert all("wind-mcp" in (item.hint or "") for item in data.missing)
    assert any("wind-mcp" in note for note in data.notes)
    assert data.providers == {}
    assert profile_provider.calls == []
    assert financials_provider.calls == []
    assert quote_provider.calls == []


@pytest.mark.asyncio
async def test_sections_subset_fetches_only_needed_sources():
    profile_provider = _FakeProvider(
        "eastmoney",
        {
            "get_company_survey": _survey(),
            "get_shareholders": _holders(),
            "get_capital_structure": CapitalStructure(total_shares=1),
            "get_business_composition": _composition(),
        },
    )
    financials_provider = _FakeProvider("akshare", {})
    quote_provider = _FakeProvider("tencent", {})
    service = StockFundamentalSnapshotService(
        profile_provider=profile_provider,
        financials_provider=financials_provider,
        quote_provider=quote_provider,
    )

    response = await service.get_snapshot(
        FundamentalSnapshotRequest(symbol="600519", sections=["meta", "shareholders"])
    )
    data = response.data

    assert data.meta is not None
    assert data.shareholders is not None
    assert data.quote_valuation is None
    assert data.profitability is None
    # 只拉了 meta/shareholders 需要的源
    assert set(profile_provider.calls) == {
        "get_company_survey",
        "get_capital_structure",
        "get_shareholders",
    }
    assert financials_provider.calls == []
    assert quote_provider.calls == []
    # 无失败块，missing 只剩静态能力缺口
    assert all(item.hint is not None for item in data.missing)


@pytest.mark.asyncio
async def test_invalid_symbol_raises_provider_error():
    with pytest.raises(ProviderError) as raised:
        await _service().get_snapshot(FundamentalSnapshotRequest(symbol="not-a-symbol"))

    assert raised.value.error_type == ErrorType.INVALID_SYMBOL
