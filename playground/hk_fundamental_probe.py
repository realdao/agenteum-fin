"""港股基本面数据源探针（stock_fundamental_snapshot P1 可行性评估，2026-07-24）。

测试标的：腾讯控股（00700.HK）。评估各快照 block 的候选数据源覆盖度：

- akshare 东财港股接口：主要指标（年度/报告期）、三大报表、公司资料、证券资料、最新指标
- 东财 datacenter RPT_HKF10_*：经营评述、主要股东、股本结构
- 腾讯行情（现有 provider）：PE(TTM)/PB/市值/币种

运行：.venv\\Scripts\\python.exe playground\\hk_fundamental_probe.py
结果写入 playground/hk_fundamental_probe_results.json（已 gitignore）。
"""

from __future__ import annotations

import asyncio
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

warnings.filterwarnings("ignore")

RESULTS_PATH = Path(__file__).with_name("hk_fundamental_probe_results.json")
DATACENTER_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
EM_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"}
CODE = "00700"
SECUCODE = "00700.HK"


def _run_akshare_section() -> dict[str, Any]:
    import akshare as ak

    out: dict[str, Any] = {}

    def capture(name: str, func, *args, **kwargs) -> None:
        try:
            df = func(*args, **kwargs)
            out[name] = {
                "ok": True,
                "shape": list(df.shape),
                "columns": [str(c) for c in df.columns][:40],
            }
            if "REPORT_DATE" in df.columns:
                out[name]["periods"] = sorted(
                    {str(d)[:10] for d in df["REPORT_DATE"]}, reverse=True
                )[:8]
            if "STD_ITEM_NAME" in df.columns:
                out[name]["items"] = [str(i) for i in df["STD_ITEM_NAME"].unique()]
            if df.shape[0] == 1:
                out[name]["sample"] = {
                    str(k): (None if v is None else str(v)[:120])
                    for k, v in df.iloc[0].to_dict().items()
                }
        except Exception as exc:  # noqa: BLE001 - 探针需要记录所有失败
            out[name] = {"ok": False, "error": repr(exc)[:200]}

    capture(
        "main_indicator_yearly",
        ak.stock_financial_hk_analysis_indicator_em,
        symbol=CODE,
        indicator="年度",
    )
    capture(
        "main_indicator_report",
        ak.stock_financial_hk_analysis_indicator_em,
        symbol=CODE,
        indicator="报告期",
    )
    for stmt in ("资产负债表", "利润表", "现金流量表"):
        capture(
            f"report_{stmt}",
            ak.stock_financial_hk_report_em,
            stock=CODE,
            symbol=stmt,
            indicator="年度",
        )
    capture("company_profile", ak.stock_hk_company_profile_em, symbol=CODE)
    capture("security_profile", ak.stock_hk_security_profile_em, symbol=CODE)
    capture("latest_indicator", ak.stock_hk_financial_indicator_em, symbol=CODE)
    return out


def _run_eastmoney_section() -> dict[str, Any]:
    out: dict[str, Any] = {}
    candidates = [
        "RPT_HKF10_ORG_BUSSINESS",
        "RPT_HKF10_EQUITYCHG_HOLDER",
        "RPT_HKF10_INFO_EQUITYSTR",
        "RPT_HKF10_MAIN_DIVBASIC",
    ]
    with httpx.Client(headers=EM_HEADERS, timeout=20) as client:
        for name in candidates:
            try:
                payload = client.get(
                    DATACENTER_URL,
                    params={
                        "reportName": name,
                        "columns": "ALL",
                        "filter": '(SECUCODE="00700.HK")',
                        "pageNumber": "1",
                        "pageSize": "5",
                        "source": "F10",
                        "client": "PC",
                    },
                ).json()
                result = payload.get("result") or {}
                rows = result.get("data") or []
                out[name] = {
                    "ok": True,
                    "count": result.get("count"),
                    "keys": sorted(rows[0].keys()) if rows else [],
                    "sample": {
                        k: (None if v is None else str(v)[:200])
                        for k, v in (rows[0] if rows else {}).items()
                    },
                }
            except Exception as exc:  # noqa: BLE001
                out[name] = {"ok": False, "error": repr(exc)[:200]}
    return out


async def _run_quote_section() -> dict[str, Any]:
    from src.providers.profile.tencent import TencentProfileProvider
    from src.utils.symbols import normalize_symbol

    async with httpx.AsyncClient(timeout=15) as client:
        profiles = await TencentProfileProvider(client=client).get_profiles(
            [normalize_symbol(SECUCODE)]
        )
    if not profiles:
        return {"ok": False, "error": "no profile returned"}
    profile = profiles[0].model_dump()
    profile["symbol"] = profile["symbol"]["display_symbol"]
    return {"ok": True, "profile": profile}


def main() -> None:
    results = {
        "generated_at": datetime.now(UTC).isoformat(),
        "symbol": SECUCODE,
        "akshare_em": _run_akshare_section(),
        "eastmoney_datacenter": _run_eastmoney_section(),
        "tencent_quote": asyncio.run(_run_quote_section()),
        "notes": [
            "iwencai hkstock 实测可返回结构化财务字段（归母/同比/毛利率/ROE/负债率），"
            "但返回字段取决于自然语言问法且消耗 quota，仅建议作兜底补充。",
            "东财港股无结构化分部收入（主营构成）接口：RPT_HKF10_ORG_BUSSINESS "
            "仅含经营评述 BUSINESS_REVIEW / 未来展望 FUTURE_EXPECT 文本。",
            "港股无扣非净利润口径；商誉/投资收益/公允价值变动在 IFRS 科目下不单列。",
        ],
    }
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    for section in ("akshare_em", "eastmoney_datacenter"):
        print(f"== {section}")
        for name, info in results[section].items():
            status = "ok " if info.get("ok") else "ERR"
            detail = info.get("shape") or f"count={info.get('count')}" or info.get("error")
            print(f"  {status} {name}: {detail}")
    quote = results["tencent_quote"]
    if quote.get("ok"):
        p = quote["profile"]
        print(
            f"== tencent_quote: price={p['price']} pe_ttm={p['pe_ttm']} pb={p['pb']} "
            f"mcap={p['market_cap']} {p['currency']}"
        )
    print(f"results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
