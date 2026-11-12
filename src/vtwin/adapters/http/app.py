"""HTTP composition without importing HTTP types into the numerical engine.

Trust boundary for run and result routes (``/api/v1/runs*``):

1. loopback bind (CLI) and ``Host`` allow-list (DNS-rebinding protection);
2. browser ``Origin`` allow-list: same origin, plus explicit loopback dev origins;
3. per-launch session token in ``X-VTwin-Session``, compared in constant time;
4. bounded request bodies, validated case contracts, bounded result pages and
   run identifiers checked against a strict pattern (no host paths).

Health, capabilities and the OpenAPI schema remain public read-only metadata.
"""

import logging
import re
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from vtwin import __version__
from vtwin.adapters.observability import register_secret, request_id_var, run_id_var
from vtwin.domain import errors
from vtwin.domain.kinematics import OBSERVABLE_IDS, OBSERVABLES

logger = logging.getLogger("vtwin.http")

SESSION_HEADER = "X-VTwin-Session"
MAX_BODY_BYTES = 64 * 1024
MAX_SERIES_PAGE = 20_000
_RUN_PATH = re.compile(r"^/api/v1/runs/(run-\d{8}T\d{6}Z-[0-9a-f]{8})(?:/|$)")
STATUS_BY_CODE = {
    "invalid_input": 422,
    "limit_exceeded": 422,
    "unsupported_model": 422,
    "unauthorized": 401,
    "forbidden_origin": 403,
    "run_not_found": 404,
    "not_found": 404,
    "method_not_allowed": 405,
    "run_state_conflict": 409,
    "workspace_busy": 409,
    "payload_too_large": 413,
    "storage_failure": 503,
    "integrity_failure": 500,
    "numerical_failure": 500,
    "internal_error": 500,
}


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
    session_header: str | None = None
    limits: dict[str, int] = Field(default_factory=dict)


@dataclass
class RunApiSettings:
    """Runtime settings of the protected run API; the token is never persisted."""

    data_dir: Path
    session_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    port: int = 8000
    dev_origins: tuple[str, ...] = ()
    run_timeout_s: float = 120.0
    log_level: str = "INFO"
    log_format: str = "json"

    def __post_init__(self) -> None:
        if len(self.session_token) < 32:
            raise errors.InvalidInput("The session token must contain at least 32 characters.")

    @property
    def allowed_origins(self) -> frozenset[str]:
        own = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        return frozenset(own | set(self.dev_origins))


def _error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "retryable": False, "details": [], **extra},
        "request_id": request_id_var.get(),
    }


def _error_response(error: errors.VTwinError) -> JSONResponse:
    payload = error.to_dict()
    if run_id_var.get():
        payload["run_id"] = run_id_var.get()
    body = {"error": payload, "request_id": request_id_var.get()}
    headers = {"Retry-After": "1"} if error.code == "workspace_busy" else None
    return JSONResponse(body, status_code=STATUS_BY_CODE.get(error.code, 500), headers=headers)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(errors.VTwinError)
    async def domain_error(_request: Request, error: errors.VTwinError) -> JSONResponse:
        level = logging.ERROR if STATUS_BY_CODE.get(error.code, 500) >= 500 else logging.INFO
        logger.log(
            level, "request_rejected", extra={"event": "request_rejected", "error_code": error.code}
        )
        return _error_response(error)

    @app.exception_handler(RequestValidationError)
    async def query_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"path": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
            for item in error.errors()
        ]
        body = _error_body("invalid_input", "Request parameters are invalid.", details=details)
        return JSONResponse(body, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "http_error")
        return JSONResponse(_error_body(code, str(error.detail)), status_code=error.status_code)

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "unhandled_error",
            exc_info=(type(error), error, error.__traceback__),
            extra={"event": "unhandled_error"},
        )
        body = _error_body("internal_error", "Unexpected server error; see the server log.")
        return JSONResponse(body, status_code=500)


Next = Callable[[Request], Awaitable[Response]]


def _declared_length(request: Request) -> int:
    try:
        return int(request.headers.get("content-length") or 0)
    except ValueError:
        return MAX_BODY_BYTES + 1  # A malformed length is treated as oversize.


def _install_middleware(app: FastAPI, settings: RunApiSettings | None) -> None:
    allowed = settings.allowed_origins if settings else frozenset()

    @app.middleware("http")
    async def guard(request: Request, call_next: Next) -> Response:
        request_token = request_id_var.set(uuid.uuid4().hex[:16])
        path = request.url.path
        match = _RUN_PATH.match(path)
        run_token = run_id_var.set(match.group(1) if match else None)
        started = time.perf_counter_ns()
        try:
            protected = path.startswith("/api/v1/runs")
            origin = request.headers.get("origin")
            if protected and origin is not None and origin not in allowed:
                response: Response = JSONResponse(
                    _error_body("forbidden_origin", "This origin may not call the run API."),
                    status_code=403,
                )
            elif request.method == "POST" and _declared_length(request) > MAX_BODY_BYTES:
                message = f"Request bodies are limited to {MAX_BODY_BYTES} bytes."
                response = JSONResponse(_error_body("payload_too_large", message), status_code=413)
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = request_id_var.get() or ""
            if protected:
                response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            logger.info(
                "http_request",
                extra={
                    "event": "http_request",
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter_ns() - started) / 1e6, 3),
                },
            )
            return response
        finally:
            run_id_var.reset(run_token)
            request_id_var.reset(request_token)

    if settings and settings.dev_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.dev_origins),
            allow_methods=["GET", "POST"],
            allow_headers=[SESSION_HEADER, "Content-Type"],
            expose_headers=["X-Request-ID", "Retry-After"],
        )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


def create_app(*, web_dir: Path | None = None, runs: RunApiSettings | None = None) -> FastAPI:
    """Build the app. Without ``runs`` only public metadata routes are exposed."""
    app = FastAPI(
        title="V-Twin local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    _install_error_handlers(app)
    _install_middleware(app, runs)

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(version=__version__)

    @app.get("/api/v1/capabilities", response_model=Capabilities)
    def capabilities() -> Capabilities:
        if runs is None:
            return Capabilities(application_version=__version__)
        return Capabilities(
            application_version=__version__,
            stage="kinematics-demo",
            simulation_available=True,
            models=["slider-crank-kinematics@1.0.0"],
            session_header=SESSION_HEADER,
            limits={"max_body_bytes": MAX_BODY_BYTES, "max_series_page": MAX_SERIES_PAGE},
        )

    if runs is not None:
        _install_run_routes(app, runs)

    if web_dir is not None:
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


def _install_run_routes(app: FastAPI, settings: RunApiSettings) -> None:
    from vtwin.adapters.execution.local import LocalCoordinator
    from vtwin.bootstrap import compute_in_worker, create_run_service

    register_secret(settings.session_token)
    expected = settings.session_token.encode()
    coordinator = LocalCoordinator(
        create_run_service(settings.data_dir),
        settings.data_dir,
        compute_in_worker,
        timeout_s=settings.run_timeout_s,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )
    app.state.coordinator = coordinator
    app.router.on_shutdown.append(coordinator.close)
    service = coordinator.service

    def require_session(request: Request) -> None:
        supplied = request.headers.get(SESSION_HEADER, "").encode()
        if not secrets.compare_digest(supplied, expected):
            raise _Unauthorized("Missing or invalid session token.")

    Session = Annotated[None, Depends(require_session)]

    def links(run_id: str) -> dict[str, str]:
        base = f"/api/v1/runs/{run_id}"
        return {"self": base, "manifest": f"{base}/manifest", "series": f"{base}/series"}

    def bound(run_id: str) -> str:
        service.store.location(run_id)  # RunNotFound for unknown or malformed identifiers
        return run_id

    @app.post("/api/v1/runs", status_code=202, tags=["runs"])
    async def submit_run(request: Request, _: Session) -> dict[str, Any]:
        """Validate and persist a ``vtwin.kinematic-case`` 1.0.0 document, then execute it."""
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY_BYTES:
                raise errors.LimitExceeded(f"Request bodies are limited to {MAX_BODY_BYTES} bytes.")
        record = coordinator.submit(bytes(body))
        run_id_var.set(record.run_id)
        return {"run": record.to_dict(), "links": links(record.run_id)}

    @app.get("/api/v1/runs", tags=["runs"])
    def list_runs(_: Session, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict[str, Any]:
        ids = sorted(service.store.list_runs(), reverse=True)[:limit]
        return {
            "runs": [service.status(run_id).to_dict() for run_id in ids],
            "active_run": coordinator.active_run,
        }

    @app.get("/api/v1/runs/{run_id}", tags=["runs"])
    def run_status(run_id: str, _: Session) -> dict[str, Any]:
        return {"run": service.status(bound(run_id)).to_dict(), "links": links(run_id)}

    @app.get("/api/v1/runs/{run_id}/manifest", tags=["runs"])
    def run_manifest(run_id: str, _: Session) -> dict[str, Any]:
        return service.store.read_manifest(bound(run_id))

    @app.get("/api/v1/runs/{run_id}/events", tags=["runs"])
    def run_events(run_id: str, _: Session) -> dict[str, Any]:
        return {"run_id": run_id, "events": service.store.read_events(bound(run_id))[-200:]}

    @app.get("/api/v1/runs/{run_id}/series", tags=["runs"])
    def run_series(
        run_id: str,
        _: Session,
        observables: Annotated[str | None, Query(max_length=200)] = None,
        start: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=MAX_SERIES_PAGE)] = 5_000,
    ) -> dict[str, Any]:
        record = service.status(bound(run_id))
        if record.state.value != "completed":
            raise errors.RunStateConflict(
                f"{run_id} is {record.state.value}; series are published on completion."
            )
        names = OBSERVABLE_IDS if not observables else tuple(observables.split(","))
        unknown = [name for name in names if name not in OBSERVABLE_IDS]
        if unknown:
            raise errors.InvalidInput(
                "Unknown observable.",
                details=[errors.FieldIssue("observables", f"Unknown: {', '.join(unknown)}.")],
            )
        stop = min(start + limit, record.total_samples)
        arrays = service.store.read_series(run_id, names, start, stop)
        units = {item.id: item.unit for item in OBSERVABLES}
        count = max(stop - start, 0)
        return {
            "run_id": run_id,
            "start": start,
            "count": count,
            "total_samples": record.total_samples,
            "next_start": stop if stop < record.total_samples else None,
            "reduction": None,
            "series": {
                name: {"unit": units[name], "values": arrays[name].tolist()} for name in names
            },
        }

    @app.post("/api/v1/runs/{run_id}/resume", status_code=202, tags=["runs"])
    def resume_run(run_id: str, _: Session) -> dict[str, Any]:
        record = coordinator.resume(bound(run_id))
        return {"run": record.to_dict(), "links": links(run_id)}


class _Unauthorized(errors.VTwinError):
    code = "unauthorized"
