"""Live probe: tencent fqkline for on-exchange funds and indices.

验证 stock_kline 的基金/指数扩展（260817 用户反馈场景）：
- ETF：561360 / 159870 / 159698（反馈原案例）
- 指数：399365 国证粮食（裸码）、000300.SH 沪深300、000001.SH 上证指数（显式后缀）

走与 MCP 工具完全相同的链路（normalize_symbol -> StockKlineService ->
TencentKlineProvider），不消耗问财额度。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from src.schemas import KlineRequest
from src.services.stock_kline_service import StockKlineService

OUT = Path(__file__).with_name("fund_index_kline_probe_results.json")

CASES: list[dict[str, str]] = [
    {"symbol": "561360", "note": "沪市 ETF 裸码"},
    {"symbol": "159870", "note": "深市 ETF 裸码"},
    {"symbol": "159698", "note": "深市 ETF 裸码"},
    {"symbol": "399365", "note": "国证粮食指数 裸码"},
    {"symbol": "000300.SH", "note": "沪深300 显式后缀"},
    {"symbol": "000001.SH", "note": "上证指数 显式后缀"},
    {"symbol": "600519", "note": "个股 对照组"},
]


async def probe(symbol: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        from src.providers.market_data.tencent_kline import TencentKlineProvider

        service = StockKlineService(
            a_share_provider=TencentKlineProvider(client=client),
            hk_provider=None,
        )
        try:
            response = await service.get_kline(
                KlineRequest(symbol=symbol, period="day", adjust="none", limit=5)
            )
            bars = response.data.bars
            return {
                "status": "ok",
                "exchange": response.data.symbol.exchange,
                "asset_type": response.data.symbol.asset_type,
                "bar_count": len(bars),
                "first_bar": bars[0].model_dump() if bars else None,
                "last_bar": bars[-1].model_dump() if bars else None,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }


async def main() -> None:
    results = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cases": [],
    }
    for case in CASES:
        outcome = await probe(case["symbol"])
        entry = {**case, **outcome}
        results["cases"].append(entry)
        print(json.dumps(entry, ensure_ascii=False))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
