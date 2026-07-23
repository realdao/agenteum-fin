import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.fundamental.eastmoney import EastmoneyFundamentalProvider
from src.utils.symbols import normalize_symbol

SYMBOL = normalize_symbol("600519")


def _provider(handler) -> EastmoneyFundamentalProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return EastmoneyFundamentalProvider(client=client)


def _route(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "CompanySurvey/PageAjax" in url:
        return httpx.Response(
            200,
            json={
                "jbzl": [
                    {
                        "SECUCODE": "600519.SH",
                        "SECURITY_NAME_ABBR": "贵州茅台",
                        "ORG_NAME": "贵州茅台酒股份有限公司",
                        "TRADE_MARKET": "上海证券交易所",
                        "EM2016": "食品饮料-饮料-白酒",
                        "INDUSTRYCSRC1": "制造业-酒、饮料和精制茶制造业",
                        "CHAIRMAN": "陈华",
                        "PRESIDENT": "王莉(代)",
                        "SECRETARY": "余思明",
                        "LEGAL_PERSON": "陈华",
                        "REG_ADDRESS": "贵州省仁怀市茅台镇",
                        "ADDRESS": "贵州省仁怀市茅台镇",
                        "EMP_NUM": 34992,
                        "ORG_WEB": "www.moutaichina.com",
                        "ORG_PROFILE": "茅台公司简介正文。",
                        "BUSINESS_SCOPE": "茅台酒及系列酒的生产与销售。",
                    }
                ],
                "fxxg": [
                    {
                        "FOUND_DATE": "1999-11-20 00:00:00",
                        "LISTING_DATE": "2001-08-27 00:00:00",
                    }
                ],
            },
        )
    if "ShareholderResearch/PageAjax" in url:
        return httpx.Response(
            200,
            json={
                "gdrs": [
                    {
                        "END_DATE": "2026-03-31 00:00:00",
                        "HOLDER_TOTAL_NUM": 243159,
                        "TOTAL_NUM_RATIO": -4.9759,
                    }
                ],
                "sjkzr": [
                    {"HOLDER_NAME": "贵州省人民政府国有资产监督管理委员会", "HOLD_RATIO": None}
                ],
                "sdgd": [
                    {
                        "END_DATE": "2026-03-31 00:00:00",
                        "HOLDER_RANK": 1,
                        "HOLDER_NAME": "中国贵州茅台酒厂(集团)有限责任公司",
                        "HOLDER_TYPE": "流通A股",
                        "HOLD_NUM": 681282935,
                        "HOLD_NUM_RATIO": 54.4,
                        "HOLD_NUM_CHANGE": "不变",
                    }
                ],
                "sdltgd": [
                    {
                        "END_DATE": "2026-03-31 00:00:00",
                        "HOLDER_RANK": 1,
                        "HOLDER_NAME": "中国贵州茅台酒厂(集团)有限责任公司",
                        "HOLD_NUM": 681282935,
                        "FREE_HOLDNUM_RATIO": 54.4038,
                        "HOLD_NUM_CHANGE": "不变",
                    }
                ],
            },
        )
    if "CapitalStockStructure/PageAjax" in url:
        return httpx.Response(
            200,
            json={
                "gbjg": [
                    {
                        "TOTAL_SHARES": 1250081601,
                        "LIMITED_SHARES": 0,
                        "UNLIMITED_SHARES": 1250081601,
                    }
                ]
            },
        )
    if "BusinessAnalysis/PageAjax" in url:
        return httpx.Response(
            200,
            json={
                "zygcfx": [
                    {
                        "REPORT_DATE": "2025-12-31 00:00:00",
                        "MAINOP_TYPE": "1",
                        "ITEM_NAME": "酒类",
                        "MAIN_BUSINESS_INCOME": 168774585187.65,
                        "MBI_RATIO": 0.999624,
                        "MAIN_BUSINESS_COST": 14805900139.59,
                        "MAIN_BUSINESS_RPOFIT": 153968685048.06,
                        "GROSS_RPOFIT_RATIO": 0.912274,
                        "RANK": 1,
                    },
                    {
                        "REPORT_DATE": "2025-12-31 00:00:00",
                        "MAINOP_TYPE": "2",
                        "ITEM_NAME": "其他系列酒",
                        "MAIN_BUSINESS_INCOME": 22274678707.16,
                        "MBI_RATIO": 0.131929,
                        "MAIN_BUSINESS_COST": 5321142314.05,
                        "MAIN_BUSINESS_RPOFIT": 16953536393.11,
                        "GROSS_RPOFIT_RATIO": 0.761112,
                        "RANK": 2,
                    },
                    {
                        "REPORT_DATE": "2025-12-31 00:00:00",
                        "MAINOP_TYPE": "2",
                        "ITEM_NAME": "茅台酒",
                        "MAIN_BUSINESS_INCOME": 146499906480.49,
                        "MBI_RATIO": 0.867695,
                        "MAIN_BUSINESS_COST": 9484757825.54,
                        "MAIN_BUSINESS_RPOFIT": 137015148654.95,
                        "GROSS_RPOFIT_RATIO": 0.935258,
                        "RANK": 1,
                    },
                    {
                        "REPORT_DATE": "2025-06-30 00:00:00",
                        "MAINOP_TYPE": "1",
                        "ITEM_NAME": "酒类",
                        "MAIN_BUSINESS_INCOME": 80000000000,
                        "MBI_RATIO": 1,
                        "MAIN_BUSINESS_COST": 7000000000,
                        "MAIN_BUSINESS_RPOFIT": 73000000000,
                        "GROSS_RPOFIT_RATIO": 0.9125,
                        "RANK": 1,
                    },
                ]
            },
        )
    return httpx.Response(404, text="not found")


@pytest.mark.asyncio
async def test_company_survey_maps_profile_and_listing_fields():
    survey = await _provider(_route).get_company_survey(SYMBOL)

    assert survey.name == "贵州茅台"
    assert survey.full_name == "贵州茅台酒股份有限公司"
    assert survey.industry_sw == "食品饮料-饮料-白酒"
    assert survey.industry_csrc == "制造业-酒、饮料和精制茶制造业"
    assert survey.chairman == "陈华"
    assert survey.employees == 34992
    assert survey.introduction == "茅台公司简介正文。"
    assert survey.business_scope == "茅台酒及系列酒的生产与销售。"
    assert survey.founded_date == "1999-11-20"
    assert survey.listing_date == "2001-08-27"


@pytest.mark.asyncio
async def test_shareholders_maps_count_controller_and_top_holders():
    holders = await _provider(_route).get_shareholders(SYMBOL)

    assert holders.holder_count == 243159
    assert holders.holder_count_date == "2026-03-31"
    assert holders.holder_count_change_pct == -4.9759
    assert holders.controller == "贵州省人民政府国有资产监督管理委员会"
    assert holders.controller_ratio_pct is None
    assert holders.top10_date == "2026-03-31"
    assert holders.top10[0].name == "中国贵州茅台酒厂(集团)有限责任公司"
    assert holders.top10[0].ratio_pct == 54.4
    # "不变" 等文本变动描述不进入数值字段
    assert holders.top10[0].change_shares is None
    assert holders.top10_float[0].ratio_pct == 54.4038


@pytest.mark.asyncio
async def test_capital_structure_maps_share_counts():
    capital = await _provider(_route).get_capital_structure(SYMBOL)

    assert capital.total_shares == 1250081601
    assert capital.limited_shares == 0
    assert capital.float_shares == 1250081601


@pytest.mark.asyncio
async def test_business_composition_uses_latest_period_and_converts_units():
    composition = await _provider(_route).get_business_composition(SYMBOL)

    assert composition.period == "2025-12-31"
    # 按行业
    industry = composition.by_industry[0]
    assert industry.name == "酒类"
    assert industry.revenue_yi == pytest.approx(1687.7459, abs=0.0001)
    assert industry.cost_yi == pytest.approx(148.059, abs=0.001)
    assert industry.gross_margin_pct == pytest.approx(91.23, abs=0.01)
    assert industry.revenue_pct == pytest.approx(99.96, abs=0.01)
    # 按产品按 RANK 排序，茅台酒在前；更早的报告期被丢弃
    assert [item.name for item in composition.by_product] == ["茅台酒", "其他系列酒"]
    assert composition.by_region == []


@pytest.mark.asyncio
async def test_empty_payloads_raise_market_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    provider = _provider(handler)
    for method in (
        provider.get_company_survey,
        provider.get_shareholders,
        provider.get_capital_structure,
        provider.get_business_composition,
    ):
        with pytest.raises(ProviderError) as raised:
            await method(SYMBOL)
        assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_timeout_propagates_as_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    provider = _provider(handler)
    with pytest.raises(ProviderError) as raised:
        await provider.get_company_survey(SYMBOL)
    assert raised.value.error_type == ErrorType.TIMEOUT
