from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from src.schemas import AnnouncementItem
from src.utils.http import post_form_json
from src.utils.symbols import NormalizedSymbol


CNINFO_BASE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"


class CninfoAnnouncementProvider:
    name = "cninfo"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

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
                "stock": f"{symbol.symbol},{_org_id(symbol)}",
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
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.cninfo.com.cn/new/disclosure",
                "Origin": "https://www.cninfo.com.cn",
            },
        )
        return [_map_announcement(item) for item in payload.get("announcements") or []]


def _org_id(symbol: NormalizedSymbol) -> str:
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
