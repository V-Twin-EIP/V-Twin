"""Protected run API: trust boundary, validation, supervised execution and diagnostics."""

import asyncio
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient, Response

from vtwin.adapters.http.app import RunApiSettings, create_app
from vtwin.adapters.observability import configure_logging
from vtwin.adapters.storage.filesystem import FileRunStore, WorkspaceLock
from vtwin.domain.errors import WorkspaceBusy

TOKEN = "t" * 43
AUTH = {"X-VTwin-Session": TOKEN}
CASE = (
    Path(__file__).resolve().parents[1] / "examples/cases/kinematics-ref-2000rpm.json"
).read_bytes()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def log_stream() -> io.StringIO:
    stream = io.StringIO()
    configure_logging("INFO", "json", stream=stream)
    return stream


def make_client(tmp_path: Path, **settings: Any) -> tuple[AsyncClient, Any]:
    app = create_app(
        runs=RunApiSettings(data_dir=tmp_path, session_token=TOKEN, port=8000, **settings)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000")
    return client, app


@pytest.fixture
async def api(tmp_path: Path, log_stream: io.StringIO) -> AsyncIterator[AsyncClient]:
    client, app = make_client(tmp_path)
    async with client:
        yield client
    app.state.coordinator.close()


async def wait_terminal(client: AsyncClient, run_id: str, timeout_s: float = 60) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        run: dict[str, Any] = (await client.get(f"/api/v1/runs/{run_id}", headers=AUTH)).json()[
            "run"
        ]
        if run["state"] in {"completed", "failed", "interrupted"}:
            return run
        assert asyncio.get_running_loop().time() < deadline, run
        await asyncio.sleep(0.05)


async def submit(client: AsyncClient, body: bytes = CASE) -> Response:
    return await client.post(
        "/api/v1/runs", content=body, headers={**AUTH, "Content-Type": "application/json"}
    )


@pytest.mark.anyio
async def test_valid_case_completes_and_results_are_bounded(api: AsyncClient) -> None:
    capabilities = (await api.get("/api/v1/capabilities")).json()
    assert capabilities["simulation_available"] is True
    assert capabilities["session_header"] == "X-VTwin-Session"

    accepted = await submit(api)
    assert accepted.status_code == 202
    run_id = accepted.json()["run"]["run_id"]
    assert accepted.json()["run"]["state"] == "queued"
    run = await wait_terminal(api, run_id)
    assert run["state"] == "completed", run
    assert run["kpis"]["simulation_rate_s_per_s"] > 0

    page = (
        await api.get(
            f"/api/v1/runs/{run_id}/series",
            params={"observables": "crank_angle_rad,piston_velocity_m_s", "limit": 500},
            headers=AUTH,
        )
    ).json()
    assert page["count"] == 500 and page["next_start"] == 500 and page["total_samples"] == 721
    assert page["series"]["piston_velocity_m_s"]["unit"] == "m/s"
    assert set(page["series"]) == {"crank_angle_rad", "piston_velocity_m_s"}
    rest = (
        await api.get(f"/api/v1/runs/{run_id}/series", params={"start": 500}, headers=AUTH)
    ).json()
    assert rest["count"] == 221 and rest["next_start"] is None

    manifest = (await api.get(f"/api/v1/runs/{run_id}/manifest", headers=AUTH)).json()
    assert manifest["model"]["version"] == "1.0.0"
    events = (await api.get(f"/api/v1/runs/{run_id}/events", headers=AUTH)).json()["events"]
    assert [item["event"] for item in events][-1] == "run_completed"
    listed = (await api.get("/api/v1/runs", headers=AUTH)).json()
    assert listed["runs"][0]["run_id"] == run_id


@pytest.mark.anyio
async def test_run_routes_require_the_session_token(api: AsyncClient) -> None:
    for headers in ({}, {"X-VTwin-Session": "wrong"}, {"X-VTwin-Session": TOKEN[:-1]}):
        response = await api.post("/api/v1/runs", content=CASE, headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert (await api.get("/api/v1/runs", headers=headers)).status_code == 401
    assert (await api.get("/health")).status_code == 200


@pytest.mark.anyio
async def test_foreign_browser_origins_are_rejected(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/runs", content=CASE, headers={**AUTH, "Origin": "http://evil.example"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"
    same_origin = await api.get("/api/v1/runs", headers={**AUTH, "Origin": "http://127.0.0.1:8000"})
    assert same_origin.status_code == 200
    assert same_origin.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_dev_origin_is_allowed_only_when_configured(tmp_path: Path) -> None:
    client, app = make_client(tmp_path, dev_origins=("http://localhost:5173",))
    async with client:
        preflight = await client.options(
            "/api/v1/runs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-VTwin-Session",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = await client.get(
            "/api/v1/runs", headers={**AUTH, "Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
    app.state.coordinator.close()


@pytest.mark.anyio
async def test_invalid_and_oversize_requests_are_refused_without_creating_runs(
    api: AsyncClient, tmp_path: Path
) -> None:
    document = json.loads(CASE)
    document["sampling"]["samples_per_revolution"] = 2
    document["geometry"]["bore"]["value"] = float("nan")
    invalid = await submit(api, json.dumps(document).encode())
    assert invalid.status_code == 422
    error = invalid.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["details"][0]["message"].startswith("Non-finite JSON constant")

    document = json.loads(CASE)
    document["sampling"]["samples_per_revolution"] = 2
    invalid = await submit(api, json.dumps(document).encode())
    assert invalid.status_code == 422
    assert invalid.json()["error"]["details"] == [
        {"path": "sampling.samples_per_revolution", "message": "Must be between 4 and 7200."}
    ]
    assert (await submit(api, b"{not json")).status_code == 422
    oversize = await submit(api, b" " * (64 * 1024 + 1))
    assert oversize.status_code == 413
    assert oversize.json()["error"]["code"] == "payload_too_large"
    assert FileRunStore(tmp_path).list_runs() == []


@pytest.mark.anyio
async def test_unknown_runs_and_bad_queries_have_structured_errors(api: AsyncClient) -> None:
    for run_id in ("run-20260101T000000Z-00000000", "..%2F..%2Fetc", "nope"):
        response = await api.get(f"/api/v1/runs/{run_id}", headers=AUTH)
        assert response.status_code == 404
        # An encoded traversal no longer matches the route at all: a generic 404.
        assert response.json()["error"]["code"] in {"run_not_found", "not_found"}
        assert response.json()["request_id"]
    run_id = (await submit(api)).json()["run"]["run_id"]
    await wait_terminal(api, run_id)
    bad = await api.get(
        f"/api/v1/runs/{run_id}/series", params={"observables": "torque_nm"}, headers=AUTH
    )
    assert bad.status_code == 422
    too_many = await api.get(
        f"/api/v1/runs/{run_id}/series", params={"limit": 20_001}, headers=AUTH
    )
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "invalid_input"


@pytest.mark.anyio
async def test_one_execution_at_a_time(api: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VTWIN_FAULT_INJECTION", "delay_s=0.3")
    first = await submit(api)
    assert first.status_code == 202
    second = await submit(api)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "workspace_busy"
    assert second.headers["retry-after"] == "1"
    assert (await wait_terminal(api, first.json()["run"]["run_id"]))["state"] == "completed"


@pytest.mark.anyio
async def test_numerical_failure_is_terminal_and_readable(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VTWIN_FAULT_INJECTION", "nan_at=360")
    run_id = (await submit(api)).json()["run"]["run_id"]
    run = await wait_terminal(api, run_id)
    assert run["state"] == "failed"
    assert run["error"]["code"] == "numerical_failure"
    assert run["resumable"] is False
    series = await api.get(f"/api/v1/runs/{run_id}/series", headers=AUTH)
    assert series.status_code == 409
    assert series.json()["error"]["run_id"] == run_id
    assert (await api.post(f"/api/v1/runs/{run_id}/resume", headers=AUTH)).status_code == 409


@pytest.mark.anyio
async def test_worker_crash_is_supervised_and_the_run_resumes_identically(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reference = (await submit(api)).json()["run"]["run_id"]
    await wait_terminal(api, reference)
    monkeypatch.setenv("VTWIN_FAULT_INJECTION", "crash_at=360")
    run_id = (await submit(api)).json()["run"]["run_id"]
    run = await wait_terminal(api, run_id)
    assert run["state"] == "failed"
    assert run["error"]["code"] == "worker_failure"
    assert run["progress"]["completed_samples"] == 360
    assert run["resumable"] is True
    assert (await api.get("/health")).status_code == 200

    monkeypatch.delenv("VTWIN_FAULT_INJECTION")
    assert (await api.post(f"/api/v1/runs/{run_id}/resume", headers=AUTH)).status_code == 202
    assert (await wait_terminal(api, run_id))["state"] == "completed"
    store = FileRunStore(tmp_path)
    for name, values in store.read_series(reference).items():
        np.testing.assert_array_equal(store.read_series(run_id)[name], values)


@pytest.mark.anyio
async def test_hung_worker_is_stopped_by_the_run_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, log_stream: io.StringIO
) -> None:
    monkeypatch.setenv("VTWIN_FAULT_INJECTION", "hang_at=360")
    client, app = make_client(tmp_path, run_timeout_s=3.0)
    async with client:
        run_id = (await submit(client)).json()["run"]["run_id"]
        run = await wait_terminal(client, run_id)
    app.state.coordinator.close()
    assert run["state"] == "failed"
    assert run["error"]["code"] == "run_timeout"
    assert run["resumable"] is True


@pytest.mark.anyio
async def test_logs_are_correlated_and_never_contain_the_token(
    api: AsyncClient, log_stream: io.StringIO
) -> None:
    run_id = (await submit(api)).json()["run"]["run_id"]
    await wait_terminal(api, run_id)
    await api.get("/api/v1/runs", headers={"X-VTwin-Session": "wrong"})
    text = log_stream.getvalue()
    assert TOKEN not in text
    records = [json.loads(line) for line in text.splitlines()]
    assert all(record["session_id"] for record in records)
    queued = next(record for record in records if record.get("event") == "run_queued")
    assert queued["run_id"] == run_id and queued["request_id"]
    requests = [record for record in records if record.get("event") == "http_request"]
    assert any(record["status"] == 401 for record in requests)
    assert all("headers" not in record for record in requests)
    supervised = [record for record in records if record.get("event") == "worker_finished"]
    assert supervised and supervised[0]["run_id"] == run_id


def test_server_owns_its_workspace(tmp_path: Path) -> None:
    _, app = make_client(tmp_path)
    with pytest.raises(WorkspaceBusy):
        WorkspaceLock(tmp_path).acquire()
    with pytest.raises(WorkspaceBusy):
        make_client(tmp_path)
    app.state.coordinator.close()
