from __future__ import annotations

import json
import time
import traceback
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
OUT = Path(__file__).with_name("provider_probe_results.json")


def code_prefix(code: str) -> str:
    raw = code.strip().lower()
    if raw.startswith("hk") or raw.endswith(".hk"):
        return "hk"
    normalized = normalize_code(code)
    if normalized.startswith(("6", "9")):
        return "sh"
    if normalized.startswith(("8", "4")):
        return "bj"
    return "sz"


def normalize_code(code: str) -> str:
    value = code.strip()
    lower = value.lower()
    if lower.startswith(("sh", "sz", "bj", "hk")):
        value = value[2:]
    if "." in value:
        value = value.split(".", 1)[0]
    return value.zfill(5) if lower.startswith("hk") else value.zfill(6)


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=headers or {"User-Agent": UA}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_json(
    url: str,
    *,
    data: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    response = requests.post(url, data=data, headers=headers or {"User-Agent": UA}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def safe_float(value: str | None) -> float | None:
    if value in {None, "", "--"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def tencent_quote(codes: list[str]) -> dict[str, dict[str, Any]]:
    prefixed = []
    for raw_code in codes:
        code = normalize_code(raw_code)
        prefix = code_prefix(raw_code)
        prefixed.append(f"{prefix}{code}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as response:
        text = response.read().decode("gbk", errors="replace")

    rows = {}
    for line in text.strip().split(";"):
        if not line.strip() or '"' not in line:
            continue
        key = line.split("=", 1)[0].rsplit("_", 1)[-1]
        values = line.split('"')[1].split("~")
        if len(values) < 53:
            rows[key] = {"parse_error": f"too_few_fields:{len(values)}", "raw_prefix": values[:10]}
            continue
        rows[key] = {
            "name": values[1],
            "code": values[2],
            "price": safe_float(values[3]),
            "last_close": safe_float(values[4]),
            "change_pct": safe_float(values[32]),
            "turnover_pct": safe_float(values[38]),
            "pe_ttm": safe_float(values[39]),
            "amplitude_pct": safe_float(values[43]),
            "mcap_yi": safe_float(values[44]),
            "float_mcap_yi": safe_float(values[45]),
            "pb": safe_float(values[46]),
            "limit_up": safe_float(values[47]),
            "limit_down": safe_float(values[48]),
            "pe_static": safe_float(values[52]),
            "field_count": len(values),
        }
    return rows


def eastmoney_stock_info(code: str) -> dict[str, Any]:
    normalized = normalize_code(code)
    market_code = 1 if normalized.startswith("6") else 0
    data = get_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{market_code}.{normalized}",
        },
    ).get("data") or {}
    return {
        "code": data.get("f57"),
        "name": data.get("f58"),
        "industry": data.get("f127"),
        "total_shares": data.get("f84"),
        "float_shares": data.get("f85"),
        "mcap": data.get("f116"),
        "float_mcap": data.get("f117"),
        "list_date": str(data.get("f189", "")),
        "price": data.get("f43"),
    }


def eastmoney_hk_stock_info(code: str) -> dict[str, Any]:
    normalized = normalize_code(f"hk{code}")
    data = get_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f43,f44,f45,f46,f47,f48,f60,f116,f117,f127",
            "secid": f"116.{normalized}",
        },
    ).get("data") or {}
    return {
        "code": data.get("f57"),
        "name": data.get("f58"),
        "price": data.get("f43"),
        "high": data.get("f44"),
        "low": data.get("f45"),
        "open": data.get("f46"),
        "volume": data.get("f47"),
        "amount": data.get("f48"),
        "last_close": data.get("f60"),
        "mcap": data.get("f116"),
        "float_mcap": data.get("f117"),
        "industry": data.get("f127"),
    }


def baidu_kline_with_ma(code: str) -> dict[str, Any]:
    data = get_json(
        "https://finance.pae.baidu.com/selfselect/getstockquotation",
        params={
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": normalize_code(code),
            "start_time": "",
            "ktype": "1",
        },
        headers={
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        },
    )
    md = (data.get("Result") or {}).get("newMarketData") or {}
    rows = [row for row in str(md.get("marketData", "")).split(";") if row]
    return {
        "result_code": data.get("ResultCode"),
        "keys": md.get("keys", []),
        "row_count": len(rows),
        "latest_rows": rows[-3:],
    }


def eastmoney_kline(code: str, klt: int = 101) -> dict[str, Any]:
    normalized = normalize_code(code)
    market_code = 1 if normalized.startswith("6") else 0
    data = get_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": f"{market_code}.{normalized}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": str(klt),
            "fqt": "1",
            "beg": "20200101",
            "end": "20500101",
            "lmt": "5",
        },
    )
    item = data.get("data") or {}
    return {"name": item.get("name"), "code": item.get("code"), "klines": item.get("klines", [])}


def eastmoney_hk_kline(code: str, klt: int = 101) -> dict[str, Any]:
    normalized = normalize_code(f"hk{code}")
    data = get_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": f"116.{normalized}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": str(klt),
            "fqt": "1",
            "beg": "20200101",
            "end": "20500101",
            "lmt": "5",
        },
    )
    item = data.get("data") or {}
    return {"name": item.get("name"), "code": item.get("code"), "klines": item.get("klines", [])}


def eastmoney_reports(code: str) -> dict[str, Any]:
    data = get_json(
        "https://reportapi.eastmoney.com/report/list",
        params={
            "industryCode": "*",
            "pageSize": "10",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": "2000-01-01",
            "endTime": "2030-01-01",
            "pageNo": "1",
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": normalize_code(code),
            "rcode": "",
            "p": "1",
            "pageNum": "1",
            "pageNumber": "1",
        },
        headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"},
        timeout=30,
    )
    rows = data.get("data") or []
    return {
        "count": len(rows),
        "total_page": data.get("TotalPage"),
        "sample": [
            {
                "title": item.get("title"),
                "publish_date": str(item.get("publishDate", ""))[:10],
                "org": item.get("orgSName"),
                "rating": item.get("emRatingName"),
                "eps_this_year": item.get("predictThisYearEps"),
            }
            for item in rows[:3]
        ],
    }


def sina_financial_report(code: str, report_type: str) -> dict[str, Any]:
    normalized = normalize_code(code)
    prefix = "sh" if normalized.startswith("6") else "sz"
    data = get_json(
        "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
        params={
            "paperCode": f"{prefix}{normalized}",
            "source": report_type,
            "type": "0",
            "page": "1",
            "num": "3",
        },
    )
    payload = ((data.get("result") or {}).get("data") or {})
    legacy_rows = payload.get(report_type)
    if isinstance(legacy_rows, list):
        rows = legacy_rows
    else:
        report_dates = payload.get("report_date") or []
        report_list = payload.get("report_list") or {}
        rows = [
            {"report_date": item.get("date_value"), "description": item.get("date_description"), **(report_list.get(item.get("date_value")) or {})}
            for item in report_dates[:3]
            if item.get("date_value") in report_list
        ]
    return {
        "report_type": report_type,
        "report_count": payload.get("report_count"),
        "count": len(rows),
        "sample_keys": sorted(rows[0].keys())[:40] if rows else [],
        "sample": rows[:2],
    }


def cninfo_announcements(code: str) -> dict[str, Any]:
    normalized = normalize_code(code)
    if normalized.startswith("6"):
        org_id = f"gssh0{normalized}"
    elif normalized.startswith(("8", "4")):
        org_id = f"gsbj0{normalized}"
    else:
        org_id = f"gssz0{normalized}"
    data = post_json(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data={
            "stock": f"{normalized},{org_id}",
            "tabName": "fulltext",
            "pageSize": "5",
            "pageNum": "1",
            "column": "",
            "category": "",
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.cninfo.com.cn/new/disclosure",
            "Origin": "https://www.cninfo.com.cn",
        },
    )
    rows = data.get("announcements") or []
    return {
        "count": len(rows),
        "sample": [
            {
                "title": item.get("announcementTitle"),
                "type": item.get("announcementTypeName"),
                "date": item.get("announcementTime"),
                "id": item.get("announcementId"),
            }
            for item in rows[:3]
        ],
    }


def baidu_concept_blocks(code: str) -> dict[str, Any]:
    data = get_json(
        "https://finance.pae.baidu.com/api/getrelatedblock",
        params={
            "code": normalize_code(code),
            "market": "ab",
            "typeCode": "all",
            "finClientType": "pc",
        },
        headers={
            "Host": "finance.pae.baidu.com",
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        },
    )
    result = data.get("Result") or []
    tags = []
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict):
                tags.extend((block.get("list") or [])[:5])
    return {
        "result_code": data.get("ResultCode"),
        "block_count": len(result) if isinstance(result, list) else None,
        "raw_tag_count": len(tags),
        "raw_tags_sample": tags[:10],
        "note": "ResultCode 10003 was observed in this environment for getrelatedblock; keep concept blocks behind a provider interface and verify again before enabling as default.",
    }


def ths_hot_reason() -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{today}/orderby/date/orderway/desc/charset/GBK/"
    data = get_json(url, headers={"User-Agent": UA})
    rows = data.get("data") or []
    return {
        "date": today,
        "errocode": data.get("errocode"),
        "count": len(rows),
        "sample": [
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "reason": item.get("reason"),
                "change_pct": item.get("zhangfu"),
            }
            for item in rows[:5]
        ],
    }


def eastmoney_datacenter(
    report_name: str,
    *,
    filter_str: str = "",
    page_size: int = 5,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> dict[str, Any]:
    data = get_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={
            "reportName": report_name,
            "columns": "ALL",
            "filter": filter_str,
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
        },
    )
    result = data.get("result") or {}
    rows = result.get("data") or []
    return {
        "provider_message": data.get("message"),
        "count": len(rows),
        "sample_keys": sorted(rows[0].keys())[:30] if rows else [],
        "sample": rows[:2],
        "note": "Empty result can mean reportName/filter mismatch, no recent data, or provider change.",
    }


def eastmoney_stock_news(code: str) -> dict[str, Any]:
    cb = f"jQuery{int(time.time() * 1000)}"
    params = {
        "cb": cb,
        "param": json.dumps(
            {
                "uid": "",
                "keyword": normalize_code(code),
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default", "pageIndex": 1, "pageSize": 5}},
            },
            ensure_ascii=False,
        ),
        "_": str(int(time.time() * 1000)),
    }
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        "https://search-api-web.eastmoney.com/search/jsonp?" + query,
        headers={"User-Agent": UA, "Referer": "https://so.eastmoney.com/"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        text = response.read().decode("utf-8", errors="replace")
    left = text.find("(")
    right = text.rfind(")")
    data = json.loads(text[left + 1 : right]) if left >= 0 and right > left else {}
    result = data.get("result") or {}
    cms = result.get("cmsArticleWebOld") if isinstance(result, dict) else None
    articles = (cms.get("list") or []) if isinstance(cms, dict) else []
    return {
        "count": len(articles),
        "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
        "sample": [
            {
                "title": item.get("title"),
                "date": item.get("date"),
                "source": item.get("mediaName"),
                "url": item.get("url"),
            }
            for item in articles[:3]
        ],
        "note": "This endpoint returned passportWeb only for stock keywords in this environment; stock news needs further discovery or an alternate provider.",
    }


def mootdx_probe(code: str) -> dict[str, Any]:
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std")
    normalized = normalize_code(code)
    bars = client.bars(symbol=normalized, category=4, offset=5)
    finance = client.finance(symbol=normalized)
    f10 = client.F10(symbol=normalized, name="公司概况")
    return {
        "daily_bars_shape": list(getattr(bars, "shape", ())),
        "daily_bars_columns": list(getattr(bars, "columns", [])),
        "latest_daily_bar": bars.tail(1).to_dict("records")[0] if hasattr(bars, "tail") and not bars.empty else None,
        "finance_keys_sample": list(finance.keys())[:20] if isinstance(finance, dict) else [],
        "f10_length": len(f10 or ""),
        "f10_head": (f10 or "")[:200],
    }


Probe = tuple[str, Callable[[], Any]]


def run_probe(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        data = fn()
        return {
            "status": "ok",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "data": data,
        }
    except Exception as exc:
        return {
            "status": "error",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-5:],
            },
        }


def main() -> None:
    probes: list[Probe] = [
        ("tencent_quote_a_share", lambda: tencent_quote(["600519", "688017"])),
        ("tencent_quote_hk", lambda: tencent_quote(["hk00700", "hk09988"])),
        ("eastmoney_stock_info_a_share", lambda: eastmoney_stock_info("600519")),
        ("eastmoney_stock_info_hk", lambda: eastmoney_hk_stock_info("00700")),
        ("baidu_kline_with_ma_a_share", lambda: baidu_kline_with_ma("600519")),
        ("eastmoney_daily_kline_a_share", lambda: eastmoney_kline("600519")),
        ("eastmoney_daily_kline_hk", lambda: eastmoney_hk_kline("00700")),
        ("eastmoney_reports", lambda: eastmoney_reports("600519")),
        ("sina_income_statement", lambda: sina_financial_report("600519", "lrb")),
        ("sina_balance_sheet", lambda: sina_financial_report("600519", "fzb")),
        ("sina_cash_flow", lambda: sina_financial_report("600519", "llb")),
        ("cninfo_announcements", lambda: cninfo_announcements("600519")),
        ("baidu_concept_blocks", lambda: baidu_concept_blocks("600519")),
        ("ths_hot_reason", ths_hot_reason),
        ("eastmoney_margin_trading", lambda: eastmoney_datacenter("RPTA_WEB_RZRQ_GGMX", filter_str='(SCODE="600519")', sort_columns="DATE")),
        ("eastmoney_holder_num", lambda: eastmoney_datacenter("RPT_HOLDERNUMLATEST", filter_str='(SECURITY_CODE="600519")')),
        ("eastmoney_stock_news", lambda: eastmoney_stock_news("600519")),
        ("mootdx_a_share", lambda: mootdx_probe("600519")),
    ]

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": [
            "This is a live provider probe for architecture brainstorming only.",
            "Some endpoints may be trading-calendar or region sensitive.",
        ],
        "probes": {},
    }
    for name, fn in probes:
        print(f"running {name}...")
        results["probes"][name] = run_probe(name, fn)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
