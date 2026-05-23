from __future__ import annotations

import contextlib
import logging

import httpx
import uvicorn
from fastapi import FastAPI

from src.api.mcp_full import create_mcp_server
from src.api.transport import mount_mcp_streamable_http
from src.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = logging.getLogger("agenteum_fin")
    settings.validate_network_binding(logger)

    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    mcp = create_mcp_server()
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
