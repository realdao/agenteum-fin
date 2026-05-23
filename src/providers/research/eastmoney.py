from __future__ import annotations

from typing import Any

import httpx

from src.schemas import ResearchReportItem
from src.utils.http import get_json
from src.utils.symbols import NormalizedSymbol


EASTMONEY_REPORT_URL = "https://reportapi.eastmoney.com/report/list"
PDF_BASE_URL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"


class EastmoneyResearchReportProvider:
    name = "eastmoney"

    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_reports(
        self,
        symbol: NormalizedSymbol,
        page_size: int,
    ) -> list[ResearchReportItem]:
        payload = await get_json(
            self.client,
            EASTMONEY_REPORT_URL,
            provider=self.name,
            params={
                "industryCode": "*",
                "pageSize": str(page_size),
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": "1",
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": symbol.symbol,
                "rcode": "",
                "p": "1",
                "pageNum": "1",
                "pageNumber": "1",
            },
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"},
        )
        return [_map_report(item) for item in payload.get("data") or []]


def _map_report(item: dict[str, Any]) -> ResearchReportItem:
    info_code = item.get("infoCode")
    return ResearchReportItem(
        title=item.get("title"),
        publish_date=str(item.get("publishDate") or "")[:10] or None,
        institution=item.get("orgSName"),
        rating=item.get("emRatingName"),
        industry=item.get("industryName"),
        eps_forecast={
            "predict_this_year_eps": item.get("predictThisYearEps"),
            "predict_next_year_eps": item.get("predictNextYearEps"),
        },
        info_code=info_code,
        pdf_url=PDF_BASE_URL.format(info_code=info_code) if info_code else None,
    )
