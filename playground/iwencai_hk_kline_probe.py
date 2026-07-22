"""Live probe: can iwencai_query return single HK stock historical daily K-line?

Context: deciding whether HK kline needs a dedicated provider (Tencent fqkline)
or whether the iwencai flexible query layer already covers it.

Every probe sends one real query and burns quota. Results are written to
playground/iwencai_hk_kline_probe_results.json for inspection.

Run:
    uv run python playground/iwencai_hk_kline_probe.py
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.config import Settings
from src.providers.iwencai.client import IwencaiClient

OUT = Path(__file__).with_name("iwencai_hk_kline_probe_results.json")

# Multiple phrasings: iwencai is NL-driven, so coverage depends heavily on wording.
PROBES: dict[str, dict[str, str]] = {
    "market_ohlcv_10d": {
        "domain": "market",
        "query": "腾讯控股 近10个交易日 每日开盘价 收盘价 最高价 最低价 成交量",
    },
    "market_history_kline": {
        "domain": "market",
        "query": "腾讯控股 历史日K线",
    },
    "market_date_range": {
        "domain": "market",
        "query": "腾讯控股 2026年7月1日至2026年7月21日 每日开盘价 收盘价 最高价 最低价 成交量",
    },
    "hkstock_ohlcv_10d": {
        "domain": "hkstock",
        "query": "腾讯控股 近10个交易日 每日开盘价 收盘价 最高价 最低价 成交量",
    },
    "market_close_series": {
        "domain": "market",
        "query": "腾讯控股 近20个交易日每日收盘价",
    },
}


def summarize(raw: Any) -> dict[str, Any]:
    body = raw.body
    if isinstance(body, dict):
        summary: dict[str, Any] = {
            "keys": sorted(body.keys()),
            "code_count": body.get("code_count"),
            "datas_count": len(body.get("datas") or []),
        }
        datas = body.get("datas") or []
        if datas and isinstance(datas[0], dict):
            summary["first_row_keys"] = sorted(datas[0].keys())[:40]
            summary["first_row"] = datas[0]
        return summary
    return {"kind": raw.kind, "preview": str(body)[:300]}


async def run_probe(fn: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        raw = await fn()
        return {
            "status": "ok",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "trace_id": raw.trace_id,
            "data": summarize(raw),
            "raw_body": raw.body,
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


async def main() -> None:
    settings = Settings(fin_request_timeout=30.0)
    api_key = settings.resolved_iwencai_api_key
    if not api_key:
        raise SystemExit("IWENCAI API key not configured (checked via Settings/.env).")

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": [
            "Live probe: single HK stock (00700 腾讯控股) historical daily K-line via iwencai_query.",
            "Each probe sends one real query and burns quota.",
        ],
        "probes": {},
    }

    async with httpx.AsyncClient(timeout=30) as http_client:
        client = IwencaiClient(client=http_client, api_key=api_key)
        for name, probe in PROBES.items():
            print(f"running {name}: {probe['query']!r} (domain={probe['domain']})")
            results["probes"][name] = await run_probe(
                lambda probe=probe: client.query_data(
                    query=probe["query"],
                    domain=probe["domain"],
                    page=1,
                    limit=25,
                )
            )

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
