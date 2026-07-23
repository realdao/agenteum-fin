import httpx
import pytest

from src.errors import ErrorType, ProviderError
from src.providers.f10.eastmoney_f10 import EastmoneyF10Provider
from src.utils.symbols import normalize_symbol

SYMBOL = "600519"


def _provider(handler) -> EastmoneyF10Provider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return EastmoneyF10Provider(client=client)


def _route(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "CompanySurvey/PageAjax" in url:
        return httpx.Response(
            200,
            json={
                "jbzl": [
                    {
                        "SECUCODE": "600519.SH",
                        "SECURITY_CODE": "600519",
                        "SECURITY_NAME_ABBR": "贵州茅台",
                        "ORG_NAME": "贵州茅台酒股份有限公司",
                        "ORG_NAME_EN": "Kweichow Moutai Co.,Ltd.",
                        "FORMERNAME": "贵州茅台→G茅台",
                        "SECURITY_TYPE": "上交所主板A股",
                        "TRADE_MARKET": "上海证券交易所",
                        "EM2016": "食品饮料-饮料-白酒",
                        "INDUSTRYCSRC1": "制造业-酒、饮料和精制茶制造业",
                        "CHAIRMAN": "陈华",
                        "PRESIDENT": "王莉(代)",
                        "SECRETARY": "余思明",
                        "LEGAL_PERSON": "陈华",
                        "REG_ADDRESS": "贵州省仁怀市茅台镇",
                        "ADDRESS": "贵州省仁怀市茅台镇",
                        "REG_CAPITAL": 125008.1601,
                        "EMP_NUM": 34992,
                        "ORG_TEL": "0851-22386002",
                        "ORG_EMAIL": "mtdm@moutaichina.com",
                        "ORG_WEB": "www.moutaichina.com",
                        "ORG_PROFILE": "茅台公司简介正文。",
                        "BUSINESS_SCOPE": "茅台酒及系列酒的生产与销售。",
                    }
                ],
                "fxxg": [
                    {
                        "FOUND_DATE": "1999-11-20 00:00:00",
                        "LISTING_DATE": "2001-08-27 00:00:00",
                        "AFTER_ISSUE_PE": 23.93,
                        "ISSUE_WAY": "网下定价发行",
                        "PAR_VALUE": 1,
                        "TOTAL_ISSUE_NUM": 71500000,
                        "ISSUE_PRICE": 31.39,
                        "NET_RAISE_FUNDS": 2202174475,
                        "OPEN_PRICE": 34.51,
                        "CLOSE_PRICE": 35.55,
                        "HIGH_PRICE": 37.78,
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
                        "AVG_FREE_SHARES": 5150,
                        "AVG_HOLD_AMT": 7294882.5008,
                        "HOLD_FOCUS": "非常分散",
                    }
                ],
                "sjkzr": [
                    {"HOLDER_NAME": "贵州省人民政府国有资产监督管理委员会", "HOLD_RATIO": None},
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
                        "LISTED_A_SHARES": 1250081601,
                        "LIMITED_SHARES_RATIO": 0,
                        "UNLIMITED_SHARES_RATIO": None,
                        "LISTED_SHARES_RATIO": 100,
                    }
                ],
                "lngbbd": [
                    {
                        "END_DATE": "2026-05-28 00:00:00",
                        "TOTAL_SHARES": 1250081601,
                        "LISTED_A_SHARES": 1250081601,
                        "CHANGE_REASON": "回购",
                    }
                ],
            },
        )
    if "api/data/v1/get" in url:
        return httpx.Response(
            200,
            json={
                "result": {
                    "data": [
                        {
                            "REPORTDATE": "2026-03-31 00:00:00",
                            "TOTAL_OPERATE_INCOME": 54702912385.23,
                            "YSTZ": 6.336,
                            "PARENT_NETPROFIT": 27242512886.45,
                            "SJLTZ": 1.47,
                            "BASIC_EPS": 21.76,
                            "DEDUCT_BASIC_EPS": None,
                            "BPS": 216.3223,
                            "MGJYXJJE": 21.4889,
                            "XSMLL": 89.7592,
                            "WEIGHTAVG_ROE": 10.57,
                            "ASSIGNDSCRPT": None,
                        }
                    ]
                }
            },
        )
    if "np-anotice-stock.eastmoney.com/api/security/ann" in url:
        return httpx.Response(
            200,
            json={
                "data": {
                    "list": [
                        {
                            "art_code": "AN_TEST",
                            "title": "贵州茅台:2025年年度权益分派实施公告",
                            "notice_date": "2026-06-22 00:00:00",
                            "columns": [
                                {"column_code": "001002002001005", "column_name": "分配方案实施"}
                            ],
                        }
                    ]
                }
            },
        )
    return httpx.Response(404, text="not found")


@pytest.mark.asyncio
async def test_eastmoney_f10_company_profile_contains_basics_and_list_info():
    provider = _provider(_route)
    text = await provider.get_f10(normalize_symbol(SYMBOL), "company_profile")
    assert "公司概况（东方财富 F10）" in text
    assert "证券代码：600519" in text
    assert "贵州茅台" in text
    assert "Kweichow Moutai Co.,Ltd." in text
    assert "上市日期：2001-08-27" in text
    assert "发行价(元)：31.39" in text


@pytest.mark.asyncio
async def test_eastmoney_f10_shareholders_lists_top_ten_and_person_count():
    provider = _provider(_route)
    text = await provider.get_f10(normalize_symbol(SYMBOL), "shareholders")
    assert "股东研究（东方财富 F10）" in text
    assert "股东户数(户)：243159" in text
    assert "中国贵州茅台酒厂(集团)有限责任公司" in text
    assert "贵州省人民政府国有资产监督管理委员会" in text
    assert "十大流通股东" in text


@pytest.mark.asyncio
async def test_eastmoney_f10_capital_structure_shows_totals_and_history():
    provider = _provider(_route)
    text = await provider.get_f10(normalize_symbol(SYMBOL), "capital_structure")
    assert "股本结构（东方财富 F10）" in text
    assert "总股本(股)：1250081601" in text
    assert "上市A股占比(%)：100" in text
    assert "股本变动历史" in text
    assert "2026-05-28" in text
    assert "回购" in text


@pytest.mark.asyncio
async def test_eastmoney_f10_financial_analysis_renders_table_with_periods():
    provider = _provider(_route)
    text = await provider.get_f10(normalize_symbol(SYMBOL), "financial_analysis")
    assert "财务分析（东方财富 F10 主要财务指标）" in text
    assert "2026-03-31" in text
    assert "营业收入(元)" in text
    assert "加权ROE(%)" in text
    assert "54702912385.23" in text


@pytest.mark.asyncio
async def test_eastmoney_f10_latest_notice_lists_dates_and_titles():
    provider = _provider(_route)
    text = await provider.get_f10(normalize_symbol(SYMBOL), "latest_notice")
    assert "最新公告（东方财富 F10）" in text
    assert "2026-06-22" in text
    assert "贵州茅台:2025年年度权益分派实施公告" in text
    assert "分配方案实施" in text


@pytest.mark.asyncio
async def test_eastmoney_f10_hsf10_routes_to_correct_path():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _route(request)

    provider = _provider(handler)
    await provider.get_f10(normalize_symbol(SYMBOL), "shareholders")

    urls = [str(req.url) for req in captured]
    assert any("ShareholderResearch/PageAjax" in u and "code=SH600519" in u for u in urls)


@pytest.mark.asyncio
async def test_eastmoney_f10_financial_filter_uses_secucode():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _route(request)

    provider = _provider(handler)
    await provider.get_f10(normalize_symbol(SYMBOL), "financial_analysis")

    # 查询参数会被 URL-encode，过滤里实际包含 SECUCODE 形如 %22600519.SH%22。
    assert any(
        "600519.SH" in str(req.url) and "RPT_LICO_FN_CPD" in str(req.url)
        for req in captured
    )


@pytest.mark.asyncio
async def test_eastmoney_f10_notices_passes_stock_list_param():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _route(request)

    provider = _provider(handler)
    await provider.get_f10(normalize_symbol(SYMBOL), "latest_notice")

    assert any("stock_list=600519" in str(req.url) for req in captured)


@pytest.mark.asyncio
async def test_eastmoney_f10_unknown_section_raises_invalid_request():
    provider = _provider(lambda request: httpx.Response(200, json={}))
    with pytest.raises(ProviderError) as raised:
        await provider.get_f10(normalize_symbol(SYMBOL), "bogus")
    assert raised.value.error_type == ErrorType.INVALID_REQUEST


@pytest.mark.asyncio
async def test_eastmoney_f10_financial_empty_rows_raises_market_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        if "api/data/v1/get" in str(request.url):
            return httpx.Response(200, json={"result": {"data": None}})
        return _route(request)

    provider = _provider(handler)
    with pytest.raises(ProviderError) as raised:
        await provider.get_f10(normalize_symbol(SYMBOL), "financial_analysis")
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_eastmoney_f10_notices_empty_list_raises_market_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        if "np-anotice-stock" in str(request.url):
            return httpx.Response(200, json={"data": {"list": []}})
        return _route(request)

    provider = _provider(handler)
    with pytest.raises(ProviderError) as raised:
        await provider.get_f10(normalize_symbol(SYMBOL), "latest_notice")
    assert raised.value.error_type == ErrorType.MARKET_CLOSED_OR_EMPTY


@pytest.mark.asyncio
async def test_eastmoney_f10_propagates_timeout_as_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    provider = _provider(handler)
    with pytest.raises(ProviderError) as raised:
        await provider.get_f10(normalize_symbol(SYMBOL), "company_profile")
    assert raised.value.error_type == ErrorType.TIMEOUT