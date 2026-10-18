"""HTTP composition without importing HTTP types into the numerical engine."""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from vtwin import __version__


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class Capabilities(BaseModel):
    api_version: Literal["1"] = "1"
    application_version: str
    stage: str = "foundation"
    simulation_available: bool = False
    viewer_3d_available: bool = False
    models: list[str] = Field(default_factory=list)


def create_app(*, web_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="V-Twin local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(version=__version__)

    @app.get("/api/v1/capabilities", response_model=Capabilities)
    def capabilities() -> Capabilities:
        return Capabilities(application_version=__version__)

    if web_dir is not None:
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
