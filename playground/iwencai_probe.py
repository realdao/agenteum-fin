from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.providers.iwencai.client import CHANNEL_SKILL_IDS, DOMAIN_SKILL_IDS, IwencaiClient

OUT = Path(__file__).with_name("iwencai_probe_results.json")

QUERY_PROBES = {
    "finance": "同花顺营业收入",
    "market": "上证指数行情",
    "macro": "最近一期CPI",
    "industry": "A股行业估值排名",
    "business": "同花顺主营业务构成",
    "management": "前十大股东",
    "insresearch": "券商金股",
    "astock": "科技股有哪些",
    "hkstock": "港股科技股有哪些？",
    "sector": "今日涨幅最大的板块有哪些？",
    "index": "沪深300最新点位",
}

SEARCH_PROBES = {
    "news": "人工智能",
    "report": "人工智能行业研究报告",
    "announcement": "分红派息公告",
}


def summarize(raw: Any) -> dict[str, Any]:
    body = raw.body
    if isinstance(body, dict):
        summary: dict[str, Any] = {
            "keys": sorted(body.keys()),
            "code_count": body.get("code_count"),
            "datas_count": len(body.get("datas") or []),
            "data_count": len(body.get("data") or []),
        }
        datas = body.get("datas") or body.get("data") or []
        if datas and isinstance(datas[0], dict):
            summary["first_row_keys"] = sorted(datas[0].keys())[:30]
        return summary
    return {"kind": raw.kind, "preview": str(body)[:200]}


async def run_probe(name: str, fn: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
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
    api_key = os.environ.get("AGENTEUM_FIN_IWENCAI_API_KEY") or os.environ.get("IWENCAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set AGENTEUM_FIN_IWENCAI_API_KEY or IWENCAI_API_KEY first. "
            "Get a key at https://www.iwencai.com/skillhub"
        )

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": [
            "This is a live Iwencai OpenAPI probe for contract verification only.",
            "Every probe sends one real query per domain/channel and burns quota.",
        ],
        "probes": {},
    }

    async with httpx.AsyncClient(timeout=30) as http_client:
        client = IwencaiClient(client=http_client, api_key=api_key)
        for domain in DOMAIN_SKILL_IDS:
            name = f"query_{domain}"
            print(f"running {name}...")
            results["probes"][name] = await run_probe(
                name,
                lambda domain=domain: client.query_data(
                    query=QUERY_PROBES[domain],
                    domain=domain,
                    page=1,
                    limit=10,
                ),
            )
        for channel in CHANNEL_SKILL_IDS:
            name = f"search_{channel}"
            print(f"running {name}...")
            results["probes"][name] = await run_probe(
                name,
                lambda channel=channel: client.search(
                    query=SEARCH_PROBES[channel],
                    channel=channel,
                    size=10,
                ),
            )

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
