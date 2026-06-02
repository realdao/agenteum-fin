from __future__ import annotations

import contextlib
import logging

import uvicorn
from fastapi import FastAPI

from src.api.mcp_full import create_mcp_server
from src.api.transport import mount_mcp_streamable_http
from src.config import Settings, get_settings
from src.provider_factory import build_services


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = logging.getLogger("agenteum_fin")
    settings.validate_network_binding(logger)

    services = build_services(settings)
    mcp = create_mcp_server(
        kline_service=services.kline_service,
        profile_service=services.profile_service,
        financial_service=services.financial_service,
        f10_service=services.f10_service,
        announcement_service=services.announcement_service,
        research_report_service=services.research_report_service,
        news_service=services.news_service,
    )
    mcp_app = mount_mcp_streamable_http(mcp)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            try:
                yield
            finally:
                await services.http_client.aclose()

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
