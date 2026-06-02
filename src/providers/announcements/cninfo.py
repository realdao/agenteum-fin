from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from src.errors import ProviderError
from src.schemas import AnnouncementItem
from src.utils.http import get_json, post_form_json
from src.utils.symbols import NormalizedSymbol

CNINFO_BASE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
CNINFO_STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.cninfo.com.cn/new/disclosure",
}


class CninfoAnnouncementProvider:
    name = "cninfo"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client
        self._org_id_by_code: dict[str, str] | None = None

    async def get_announcements(
        self,
        symbol: NormalizedSymbol,
        page_size: int,
    ) -> list[AnnouncementItem]:
        payload = await post_form_json(
            self.client,
            CNINFO_BASE_URL,
            provider=self.name,
            data={
                "stock": f"{symbol.symbol},{await self._org_id(symbol)}",
                "tabName": "fulltext",
                "pageSize": str(page_size),
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
                **CNINFO_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.cninfo.com.cn",
            },
        )
        return [_map_announcement(item) for item in payload.get("announcements") or []]

    async def _org_id(self, symbol: NormalizedSymbol) -> str:
        org_id = await self._lookup_org_id(symbol.symbol)
        return org_id or _formula_org_id(symbol)

    async def _lookup_org_id(self, code: str) -> str | None:
        if self._org_id_by_code is None:
            try:
                payload = await get_json(
                    self.client,
                    CNINFO_STOCK_LIST_URL,
                    provider=self.name,
                    headers=CNINFO_HEADERS,
                )
            except ProviderError:
                return None
            stock_list = payload.get("stockList")
            if not isinstance(stock_list, list):
                self._org_id_by_code = {}
                return None
            self._org_id_by_code = {
                str(item["code"]): str(item["orgId"])
                for item in stock_list
                if isinstance(item, dict) and item.get("code") and item.get("orgId")
            }
        return self._org_id_by_code.get(code)


def _formula_org_id(symbol: NormalizedSymbol) -> str:
    if symbol.exchange == "sh":
        return f"gssh0{symbol.symbol}"
    if symbol.exchange == "bj":
        return f"gsbj0{symbol.symbol}"
    return f"gssz0{symbol.symbol}"


def _map_announcement(item: dict[str, Any]) -> AnnouncementItem:
    adjunct_url = item.get("adjunctUrl")
    return AnnouncementItem(
        title=item.get("announcementTitle"),
        announcement_type=item.get("announcementTypeName"),
        date=_date_from_millis(item.get("announcementTime")),
        announcement_id=item.get("announcementId"),
        url=f"{CNINFO_STATIC_BASE}{adjunct_url}" if adjunct_url else None,
    )


def _date_from_millis(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None
