"""Check the foundation API and its honest capability declarations."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vtwin.adapters.http.app import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_and_capabilities_do_not_claim_an_implemented_engine_model() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://127.0.0.1"
    ) as client:
        assert (await client.get("/health")).json()["status"] == "ok"
        response = await client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json()["stage"] == "foundation"
        assert response.json()["models"] == []
        assert response.json()["simulation_available"] is False
        assert response.json()["viewer_3d_available"] is False
        assert "/api/v1/capabilities" in (await client.get("/api/v1/openapi.json")).json()["paths"]


@pytest.mark.anyio
async def test_unrecognized_hosts_are_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://127.0.0.1"
    ) as client:
        assert (
            await client.get("/health", headers={"host": "untrusted.example"})
        ).status_code == 400


@pytest.mark.anyio
async def test_built_frontend_is_served_without_hiding_api_routes(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>V-Twin fixture</h1>", encoding="utf-8")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(web_dir=tmp_path)), base_url="http://127.0.0.1"
    ) as client:
        assert "V-Twin fixture" in (await client.get("/")).text
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/api/v1/unknown")).status_code == 404
