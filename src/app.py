from __future__ import annotations

import contextlib
import logging

import httpx
import uvicorn
from fastapi import FastAPI

from src.api.mcp_full import create_mcp_server
from src.api.transport import mount_mcp_streamable_http
from src.config import Settings, get_settings
from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.providers.f10.mootdx_f10 import MootdxF10Provider
from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.providers.profile.tencent import TencentProfileProvider
from src.providers.research.eastmoney import EastmoneyResearchReportProvider
from src.services.announcement_service import AnnouncementService
from src.services.financial_statement_service import FinancialStatementService
from src.services.research_report_service import ResearchReportService
from src.services.stock_f10_service import StockF10Service
from src.services.stock_kline_service import StockKlineService
from src.services.stock_profile_service import StockProfileService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = logging.getLogger("agenteum_fin")
    settings.validate_network_binding(logger)

    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    kline_service = StockKlineService(
        a_share_provider=MootdxKlineProvider(),
        hk_provider=None,
    )
    profile_service = StockProfileService(providers=[TencentProfileProvider(client=http_client)])
    financial_service = FinancialStatementService(
        provider=SinaFinancialStatementsProvider(client=http_client),
    )
    f10_service = StockF10Service(provider=MootdxF10Provider())
    announcement_service = AnnouncementService(
        provider=CninfoAnnouncementProvider(client=http_client),
    )
    research_report_service = ResearchReportService(
        provider=EastmoneyResearchReportProvider(client=http_client),
    )
    mcp = create_mcp_server(
        kline_service=kline_service,
        profile_service=profile_service,
        financial_service=financial_service,
        f10_service=f10_service,
        announcement_service=announcement_service,
        research_report_service=research_report_service,
    )
    mcp_app = mount_mcp_streamable_http(mcp)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            try:
                yield
            finally:
                await http_client.aclose()

    app = FastAPI(title="Agenteum Fin", lifespan=lifespan)
    app.mount("/mcp/full", mcp_app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)
