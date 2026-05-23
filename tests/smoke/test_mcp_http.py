from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings


def test_create_app_mounts_mcp_endpoint():
    app = create_app(Settings())

    paths = {route.path for route in app.routes}

    assert "/mcp/full" in paths or any(path.startswith("/mcp/full") for path in paths)


def test_health_endpoint_is_lightweight():
    app = create_app(Settings())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
