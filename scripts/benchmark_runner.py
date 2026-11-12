# ruff: noqa: E501 - report strings and table rows are kept on one line for readability
"""Load and resilience bench of the local run API, with a recorded baseline (#46).

Measured path: a Python HTTP client on loopback -> ``vtwin serve`` (coordinator)
-> one spawned worker -> published results -> paginated series retrieval and
JSON decoding. No browser and no chart rendering: browser ``run_ready_s`` stays
unmeasured and is reported as ``null`` with its reason.

Campaigns: nominal (3 warm-ups + 30 measured), stored-result reads, output-volume
ramp, concurrent-submission and status-polling stress, and resilience scenarios
(invalid/out-of-order/duplicate messages, worker crash, coordinator kill and
restart, hung worker, limits). All faults are *software* faults injected through
``VTWIN_FAULT_INJECTION``; no physical defect is simulated here.

    uv run --locked --extra api python scripts/benchmark_runner.py \
        --label raphael-m4-16gb --output benchmarks/reports/runner-api-baseline.json

``--quick`` runs the reduced development-cycle scenario (no timing thresholds).
"""

import argparse
import contextlib
import copy
import hashlib
import json
import math
import os
import platform
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "examples/cases/kinematics-ref-2000rpm.json"
PROTOCOL_VERSION = "1.0.0"
SAMPLE_INTERVAL_S = 0.05
PAGE = 20_000
TERMINAL = {"completed", "failed", "interrupted"}


def now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "median": statistics.median(ordered),
        "p95_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


# --------------------------------------------------------------------- memory
class GroupSampler:
    """Sum RSS over a process and all its descendants at each tick; keep the max."""

    def __init__(self, interval_s: float = SAMPLE_INTERVAL_S) -> None:
        self.interval_s = interval_s
        self.samples: list[tuple[float, int, int]] = []
        self.errors = 0
        self.root: psutil.Process | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def attach(self, pid: int) -> None:
        self.root = psutil.Process(pid)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            root = self.root
            if root is not None:
                total, count = 0, 0
                try:
                    processes = [root, *root.children(recursive=True)]
                except psutil.Error:
                    processes = []
                    self.errors += 1
                for process in processes:
                    try:
                        total += process.memory_info().rss
                        count += 1
                    except psutil.Error:
                        self.errors += 1
                if count:
                    self.samples.append((time.perf_counter(), total, count))
            self._stop.wait(self.interval_s)

    def peak_between(self, start: float, end: float) -> dict[str, Any]:
        window = [item for item in self.samples if start <= item[0] <= end]
        if not window:
            return {"peak_sampled_rss_bytes": None, "samples": 0, "max_processes": 0}
        return {
            "peak_sampled_rss_bytes": max(item[1] for item in window),
            "samples": len(window),
            "max_processes": max(item[2] for item in window),
        }


# --------------------------------------------------------------------- server
@dataclass
class Server:
    data_dir: Path
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    faults: str = ""
    timeout_s: float = 120.0
    sampler: GroupSampler | None = None
    process: subprocess.Popen[bytes] | None = None
    port: int = 0

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "Server":
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        env = {**os.environ, "VTWIN_SESSION_TOKEN": self.token, "VTWIN_LOG_LEVEL": "WARNING"}
        env.pop("VTWIN_FAULT_INJECTION", None)
        if self.faults:
            env["VTWIN_FAULT_INJECTION"] = self.faults
        command = [sys.executable, "-m", "vtwin", "serve", "--no-web", "--port", str(self.port)]
        command += ["--data-dir", str(self.data_dir), "--run-timeout-s", str(self.timeout_s)]
        self.process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        deadline = time.monotonic() + 30
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"Server exited with {self.process.returncode} at startup.")
            with contextlib.suppress(httpx.HTTPError):
                if httpx.get(self.base + "/health", timeout=1).status_code == 200:
                    break
            if time.monotonic() > deadline:
                raise RuntimeError("Server did not become ready.")
            time.sleep(0.05)
        if self.sampler:
            self.sampler.attach(self.process.pid)
        return self

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base, headers={"X-VTwin-Session": self.token}, timeout=30)

    def descendants(self) -> list[int]:
        assert self.process is not None
        with contextlib.suppress(psutil.Error):
            return [child.pid for child in psutil.Process(self.process.pid).children(True)]
        return []

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(5)

    def kill(self) -> list[int]:
        """SIGKILL-equivalent stop of the coordinator only; return orphan worker PIDs."""
        assert self.process is not None
        children = self.descendants()
        self.process.kill()
        self.process.wait(5)
        return children


@contextlib.contextmanager
def running(server: Server) -> Iterator[Server]:
    server.start()
    try:
        yield server
    finally:
        server.stop()


def case_document(revolutions: int = 2, per_revolution: int = 360) -> dict[str, Any]:
    document = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    document["sampling"] = {"revolutions": revolutions, "samples_per_revolution": per_revolution}
    return document


def body(document: dict[str, Any]) -> bytes:
    return json.dumps(document).encode()


def wait_terminal(client: httpx.Client, run_id: str, timeout_s: float = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        run: dict[str, Any] = client.get(f"/api/v1/runs/{run_id}").json()["run"]
        if run["state"] in TERMINAL:
            return run
        if time.monotonic() > deadline:
            raise RuntimeError(f"{run_id} did not finish: {run['state']}")
        time.sleep(0.01)


def fetch_series(client: httpx.Client, run_id: str) -> tuple[dict[str, list[float]], int]:
    """Read every page of every observable; return decoded values and response bytes."""
    values: dict[str, list[float]] = {}
    start: int | None = 0
    received = 0
    while start is not None:
        response = client.get(
            f"/api/v1/runs/{run_id}/series", params={"start": start, "limit": PAGE}
        )
        response.raise_for_status()
        received += len(response.content)
        page = response.json()
        for name, item in page["series"].items():
            values.setdefault(name, []).extend(item["values"])
        start = page["next_start"]
    return values, received


def check_kinematics(document: dict[str, Any], values: dict[str, list[float]]) -> dict[str, Any]:
    """Independent correctness guardrail on every measured result."""
    stroke = document["geometry"]["stroke"]["value"] * 1e-3
    rpm = document["operating_point"]["crank_speed"]["value"]
    per_rev = document["sampling"]["samples_per_revolution"]
    expected = document["sampling"]["revolutions"] * per_rev + 1
    x = values["piston_displacement_m"]
    v = values["piston_velocity_m_s"]
    t = values["time_s"]
    checks = {
        "sample_count": all(len(series) == expected for series in values.values()),
        "stroke": abs(max(x) - stroke) <= 1e-12 and abs(x[per_rev // 2] - stroke) <= 1e-12,
        "dead_centre_velocity": abs(v[0]) <= 1e-12 and abs(v[per_rev // 2]) <= 1e-9,
        "period": abs(t[per_rev] - 60.0 / rpm) <= 1e-12,
        "finite": all(math.isfinite(item) for series in values.values() for item in series),
    }
    return {"correct": all(checks.values()), "checks": checks}


def digest(values: dict[str, list[float]]) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------- campaigns
def measured_run(
    client: httpx.Client, document: dict[str, Any], sampler: GroupSampler
) -> dict[str, Any]:
    payload = body(document)
    t0 = time.perf_counter()
    response = client.post("/api/v1/runs", content=payload)
    t_accepted = time.perf_counter()
    if response.status_code != 202:
        return {"outcome": "rejected", "status": response.status_code, "body": response.json()}
    run_id = response.json()["run"]["run_id"]
    run = wait_terminal(client, run_id)
    t_terminal = time.perf_counter()
    if run["state"] != "completed":
        return {"outcome": run["state"], "run_id": run_id, "error": run["error"]}
    values, received = fetch_series(client, run_id)
    t_ready = time.perf_counter()
    correctness = check_kinematics(document, values)
    kpis = run["kpis"]
    return {
        "outcome": "completed" if correctness["correct"] else "incorrect",
        "run_id": run_id,
        "api_run_ready_s": t_ready - t0,
        "spans_s": {
            "submit_until_accepted": t_accepted - t0,
            "accepted_until_terminal_observed": t_terminal - t_accepted,
            "series_retrieval_and_decode": t_ready - t_terminal,
        },
        "engine_wall_s": kpis["engine_wall_s"],
        "compute_wall_s": kpis["compute_wall_s"],
        "simulated_duration_s": kpis["simulated_duration_s"],
        "simulation_rate_s_per_s": kpis["simulation_rate_s_per_s"],
        "worker_peak_rss_bytes": kpis["resources"].get("peak_rss_bytes"),
        "output_samples": kpis["output_samples"],
        "response_bytes": received,
        "memory": sampler.peak_between(t0, t_ready),
        "correctness": correctness,
    }


def nominal(server: Server, warmups: int, attempts: int) -> dict[str, Any]:
    assert server.sampler is not None
    document = case_document()
    with server.client() as client:
        idle = server.sampler.peak_between(time.perf_counter() - 1.0, time.perf_counter())
        warm = [measured_run(client, document, server.sampler) for _ in range(warmups)]
        measured = [measured_run(client, document, server.sampler) for _ in range(attempts)]
        completed = [item for item in measured if item["outcome"] == "completed"]
        reference = completed[0]["run_id"] if completed else None
        stored: list[float] = []
        if reference:
            fetch_series(client, reference)  # warm the stored-result path once
            for _ in range(attempts):
                start = time.perf_counter()
                fetch_series(client, reference)
                stored.append(time.perf_counter() - start)
    total_sim = sum(item["simulated_duration_s"] for item in completed)
    total_engine = sum(item["engine_wall_s"] for item in completed)
    peaks = [item["memory"]["peak_sampled_rss_bytes"] for item in completed]
    return {
        "workload": {"case": str(CASE_PATH.relative_to(ROOT)), "samples": 721, "observables": 4},
        "idle_before": idle,
        "warmups": warm,
        "attempts": measured,
        "outcomes": {
            outcome: sum(item["outcome"] == outcome for item in measured)
            for outcome in sorted({item["outcome"] for item in measured})
        },
        "summary": {
            "api_run_ready_s": summary([item["api_run_ready_s"] for item in completed]),
            "accepted_until_terminal_observed_s": summary(
                [item["spans_s"]["accepted_until_terminal_observed"] for item in completed]
            ),
            "series_retrieval_and_decode_s": summary(
                [item["spans_s"]["series_retrieval_and_decode"] for item in completed]
            ),
            "engine_wall_s": summary([item["engine_wall_s"] for item in completed]),
            "simulation_rate_per_attempt": summary(
                [item["simulation_rate_s_per_s"] for item in completed]
            ),
            "simulation_rate_aggregate_s_per_s": total_sim / total_engine if total_engine else None,
            "peak_sampled_app_rss_bytes": max((p for p in peaks if p), default=None),
            "stored_result_api_read_s": summary(stored),
        },
    }


def ramp(server: Server, sizes: list[tuple[int, int]], repetitions: int) -> list[dict[str, Any]]:
    assert server.sampler is not None
    results = []
    with server.client() as client:
        for revolutions, per_revolution in sizes:
            document = case_document(revolutions, per_revolution)
            runs = [measured_run(client, document, server.sampler) for _ in range(repetitions)]
            ok = [item for item in runs if item["outcome"] == "completed"]
            results.append(
                {
                    "revolutions": revolutions,
                    "samples_per_revolution": per_revolution,
                    "output_samples": revolutions * per_revolution + 1,
                    "attempts": runs,
                    "api_run_ready_s": summary([item["api_run_ready_s"] for item in ok]),
                    "engine_wall_s": summary([item["engine_wall_s"] for item in ok]),
                    "series_retrieval_and_decode_s": summary(
                        [item["spans_s"]["series_retrieval_and_decode"] for item in ok]
                    ),
                    "peak_sampled_app_rss_bytes": max(
                        (item["memory"]["peak_sampled_rss_bytes"] or 0 for item in ok), default=None
                    ),
                    "response_bytes": ok[0]["response_bytes"] if ok else None,
                }
            )
    return results


def stress(server: Server, clients: int, rounds: int, polls: int) -> dict[str, Any]:
    document = case_document(100, 3600)  # long enough to overlap concurrent requests
    payload = body(document)
    rounds_out = []
    for _ in range(rounds):
        barrier = threading.Barrier(clients)

        def submit_one(_: int, barrier: threading.Barrier = barrier) -> int:
            with server.client() as client:
                barrier.wait()
                return client.post("/api/v1/runs", content=payload).status_code

        with ThreadPoolExecutor(clients) as pool:
            statuses = list(pool.map(submit_one, range(clients)))
        with server.client() as client:
            active = client.get("/api/v1/runs").json()["active_run"]
            latencies: list[float] = []

            def poll(_: int) -> float:
                with server.client() as poller:
                    start = time.perf_counter()
                    poller.get("/health")
                    return time.perf_counter() - start

            if active:
                with ThreadPoolExecutor(clients) as pool:
                    latencies = list(pool.map(poll, range(polls)))
                run = wait_terminal(client, active)
            else:
                run = {"state": None}
        rounds_out.append(
            {
                "statuses": sorted(statuses),
                "accepted": statuses.count(202),
                "busy_rejections": statuses.count(409),
                "run_state": run["state"],
                "health_latency_during_run_s": summary(latencies),
            }
        )
    passed = all(
        item["accepted"] == 1
        and item["busy_rejections"] == clients - 1
        and item["run_state"] == "completed"
        for item in rounds_out
    )
    return {"clients": clients, "rounds": rounds_out, "passed": passed}


# ------------------------------------------------------------------ resilience
Scenario = Callable[[Path], dict[str, Any]]


def scenario_invalid_messages(work: Path) -> dict[str, Any]:
    with running(Server(work / "invalid")) as server, server.client() as client:
        document = case_document()
        nan = body(document).replace(b'"value": 86', b'"value": NaN', 1)
        version = copy.deepcopy(document)
        version["schema_version"] = "9.0.0"
        unknown = copy.deepcopy(document)
        unknown["geometry"]["piston_mass"] = {"value": 1, "unit": "kg", "source": "x"}
        over = case_document(1000, 7200)
        cases = {
            "malformed_json": (client.post("/api/v1/runs", content=b"{"), 422, "invalid_input"),
            "non_finite_number": (client.post("/api/v1/runs", content=nan), 422, "invalid_input"),
            "unsupported_version": (
                client.post("/api/v1/runs", content=body(version)),
                422,
                "unsupported_model",
            ),
            "unknown_field": (
                client.post("/api/v1/runs", content=body(unknown)),
                422,
                "invalid_input",
            ),
            "output_over_limit": (
                client.post("/api/v1/runs", content=body(over)),
                422,
                "limit_exceeded",
            ),
            "oversize_body": (
                client.post("/api/v1/runs", content=b" " * 70_000),
                413,
                "payload_too_large",
            ),
            "missing_token": (
                httpx.post(server.base + "/api/v1/runs", content=body(document)),
                401,
                "unauthorized",
            ),
            "foreign_origin": (
                client.post(
                    "/api/v1/runs",
                    content=body(document),
                    headers={"Origin": "http://evil.example"},
                ),
                403,
                "forbidden_origin",
            ),
            "foreign_host": (
                client.get("/api/v1/runs", headers={"Host": "evil.example"}),
                400,
                None,
            ),
        }
        results = {}
        for name, (response, status, code) in cases.items():
            observed = response.json()["error"]["code"] if code else None
            results[name] = {
                "status": response.status_code,
                "code": observed,
                "passed": response.status_code == status and observed == code,
            }
        runs_created = len(client.get("/api/v1/runs").json()["runs"])
        healthy = client.get("/health").status_code == 200
    return {
        "checks": results,
        "runs_created": runs_created,
        "server_healthy_after": healthy,
        "passed": all(item["passed"] for item in results.values())
        and runs_created == 0
        and healthy,
    }


def scenario_out_of_order(work: Path) -> dict[str, Any]:
    with running(Server(work / "order", faults="delay_s=0.2")) as server, server.client() as c:
        unknown = c.get("/api/v1/runs/run-20260101T000000Z-00000000").status_code
        run_id = c.post("/api/v1/runs", content=body(case_document(3))).json()["run"]["run_id"]
        early_series = c.get(f"/api/v1/runs/{run_id}/series")
        early_resume = c.post(f"/api/v1/runs/{run_id}/resume")
        final = wait_terminal(c, run_id)
        late_resume = c.post(f"/api/v1/runs/{run_id}/resume").status_code
        late_series = c.get(f"/api/v1/runs/{run_id}/series").status_code
    checks = {
        "status_of_unknown_run_404": unknown == 404,
        "series_before_completion_409": early_series.status_code == 409,
        "resume_while_running_409": early_resume.status_code == 409,
        "completed": final["state"] == "completed",
        "resume_after_completion_409": late_resume == 409,
        "series_after_completion_200": late_series == 200,
    }
    return {"checks": checks, "passed": all(checks.values())}


def scenario_duplicates(work: Path) -> dict[str, Any]:
    with running(Server(work / "duplicates")) as server, server.client() as client:
        payload = body(case_document())
        ids = []
        for _ in range(2):
            ids.append(client.post("/api/v1/runs", content=payload).json()["run"]["run_id"])
            wait_terminal(client, ids[-1])
        series = [fetch_series(client, run_id)[0] for run_id in ids]
        listed = len(client.get("/api/v1/runs").json()["runs"])
    checks = {
        "distinct_run_ids": ids[0] != ids[1],
        "identical_results": digest(series[0]) == digest(series[1]),
        "exact_sample_counts": all(len(item["time_s"]) == 721 for item in series),
        "one_record_per_accepted_submission": listed == 2,
    }
    return {"checks": checks, "run_ids": ids, "passed": all(checks.values())}


def _reference_digest(work: Path, document: dict[str, Any]) -> str:
    with running(Server(work / "reference")) as server, server.client() as client:
        run_id = client.post("/api/v1/runs", content=body(document)).json()["run"]["run_id"]
        wait_terminal(client, run_id)
        return digest(fetch_series(client, run_id)[0])


def scenario_worker_crash(work: Path) -> dict[str, Any]:
    document = case_document(4)
    reference = _reference_digest(work / "crash", document)
    data = work / "crash" / "data"
    with running(Server(data, faults="crash_at=720")) as server, server.client() as client:
        run_id = client.post("/api/v1/runs", content=body(document)).json()["run"]["run_id"]
        failed = wait_terminal(client, run_id)
        healthy = client.get("/health").status_code == 200
    with running(Server(data)) as server, server.client() as client:
        resumed = client.post(f"/api/v1/runs/{run_id}/resume").status_code
        final = wait_terminal(client, run_id)
        values = fetch_series(client, run_id)[0]
        events = [
            item["event"] for item in client.get(f"/api/v1/runs/{run_id}/events").json()["events"]
        ]
    checks = {
        "failure_recorded_as_worker_failure": (failed["error"] or {}).get("code")
        == "worker_failure",
        "committed_samples_before_crash": failed["progress"]["completed_samples"] == 720,
        "coordinator_survived": healthy,
        "resume_accepted": resumed == 202,
        "completed_after_resume": final["state"] == "completed",
        "no_double_counting": len(values["time_s"]) == 1441,
        "identical_to_uninterrupted": digest(values) == reference,
    }
    return {"checks": checks, "events": events, "passed": all(checks.values())}


def scenario_coordinator_kill(work: Path) -> dict[str, Any]:
    document = case_document(20)
    reference = _reference_digest(work / "kill", document)
    data = work / "kill" / "data"
    server = Server(data, faults="delay_s=0.05").start()
    with server.client() as client:
        run_id = client.post("/api/v1/runs", content=body(document)).json()["run"]["run_id"]
        deadline = time.monotonic() + 30
        while (
            client.get(f"/api/v1/runs/{run_id}").json()["run"]["progress"]["completed_samples"]
            < 1440
        ):
            if time.monotonic() > deadline:
                raise RuntimeError("Run did not progress before the kill.")
            time.sleep(0.01)
    orphans = server.kill()
    deadline = time.monotonic() + 10
    while any(_alive(pid) for pid in orphans) and time.monotonic() < deadline:
        time.sleep(0.05)
    orphan_alive = any(_alive(pid) for pid in orphans)
    with running(Server(data)) as restarted, restarted.client() as client:
        reconciled = client.get(f"/api/v1/runs/{run_id}").json()["run"]
        resumed = client.post(f"/api/v1/runs/{run_id}/resume").status_code
        final = wait_terminal(client, run_id)
        values = fetch_series(client, run_id)[0]
    checks = {
        "orphan_worker_exited": not orphan_alive,
        "reconciled_as_interrupted": reconciled["state"] == "interrupted",
        "killed_mid_run": 1440 <= reconciled["progress"]["completed_samples"] < 7201,
        "resume_accepted": resumed == 202,
        "completed_after_resume": final["state"] == "completed",
        "no_double_counting": len(values["time_s"]) == 7201,
        "identical_to_uninterrupted": digest(values) == reference,
    }
    return {
        "checks": checks,
        "committed_samples_at_restart": reconciled["progress"]["completed_samples"],
        "passed": all(checks.values()),
    }


def _alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def scenario_hung_worker(work: Path) -> dict[str, Any]:
    with running(Server(work / "hang", faults="hang_at=360", timeout_s=3)) as server:
        with server.client() as client:
            started = time.perf_counter()
            run_id = client.post("/api/v1/runs", content=body(case_document())).json()["run"][
                "run_id"
            ]
            run = wait_terminal(client, run_id)
            elapsed = time.perf_counter() - started
            # 1 x 720 samples: chunk starts 0 and 720, so the hang at 360 is not hit.
            next_id = client.post("/api/v1/runs", content=body(case_document(1, 720))).json()
            next_run = wait_terminal(client, next_id["run"]["run_id"])["state"]
        workers = server.descendants()
    checks = {
        "stopped_as_run_timeout": (run["error"] or {}).get("code") == "run_timeout",
        "resumable": run["resumable"] is True,
        "bounded_by_timeout": elapsed < 3 + 15,
        "coordinator_completes_next_run": next_run == "completed",
    }
    return {
        "checks": checks,
        "elapsed_s": elapsed,
        "remaining_workers": len(workers),
        "passed": all(checks.values()),
    }


SCENARIOS: dict[str, Scenario] = {
    "invalid_messages": scenario_invalid_messages,
    "out_of_order_requests": scenario_out_of_order,
    "duplicate_submissions": scenario_duplicates,
    "worker_crash_and_resume": scenario_worker_crash,
    "coordinator_kill_restart_and_resume": scenario_coordinator_kill,
    "hung_worker_timeout": scenario_hung_worker,
}


# ----------------------------------------------------------------------- main
def environment(label: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch) / "inventory.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/performance_inventory.py"),
                "--label",
                label,
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        inventory: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    return inventory


def markdown(report: dict[str, Any]) -> str:
    nominal_summary = report["nominal"]["summary"]

    def ms(entry: dict[str, Any]) -> str:
        if not entry.get("count"):
            return "n/a"
        return (
            f"{entry['median'] * 1e3:.1f} / {entry['p95_nearest_rank'] * 1e3:.1f} / "
            f"{entry['maximum'] * 1e3:.1f}"
        )

    env = report["environment"]
    lines = [
        f"# Runner API baseline — {report['captured_at_utc'][:10]}",
        "",
        f"**Path measured:** {report['path_measured']}. **Machine:** `{env['machine_label']}` "
        f"({env['hardware']['cpu_model']}, {env['hardware']['physical_memory_bytes'] / 2**30:.0f} GiB, "
        f"{env['hardware']['os']} {env['hardware']['os_release']}). **Commit:** `{env['source']['commit']}`"
        f"{' (dirty worktree)' if env['source']['worktree_dirty'] else ''}. "
        f"**Mode:** {'quick (reduced)' if report['quick'] else 'full'}.",
        "",
        "Generated by `scripts/benchmark_runner.py`; raw attempts are in the JSON file of the same name.",
        "",
        "## Nominal case (2 revolutions x 360 samples, 4 observables)",
        "",
        f"Outcomes of measured attempts: {report['nominal']['outcomes']}. "
        f"Warm-ups: {len(report['nominal']['warmups'])}.",
        "",
        "| Measure | median / p95 / max (ms) |",
        "| :--- | :--- |",
        f"| API run ready (submit → series decoded) | {ms(nominal_summary['api_run_ready_s'])} |",
        f"| Accepted → terminal state observed | {ms(nominal_summary['accepted_until_terminal_observed_s'])} |",
        f"| Series retrieval and decode | {ms(nominal_summary['series_retrieval_and_decode_s'])} |",
        f"| Engine wall time | {ms(nominal_summary['engine_wall_s'])} |",
        f"| Stored result read (API, no rendering) | {ms(nominal_summary['stored_result_api_read_s'])} |",
        "",
        f"Aggregate simulation rate: {nominal_summary['simulation_rate_aggregate_s_per_s']:.1f} s_sim/s_wall "
        "(total simulated duration / total engine wall time). "
        f"Peak sampled RSS of coordinator + worker: "
        f"{(nominal_summary['peak_sampled_app_rss_bytes'] or 0) / 2**20:.0f} MiB "
        f"({SAMPLE_INTERVAL_S * 1e3:.0f} ms sampling, browser excluded).",
        "",
        "## Output-volume ramp",
        "",
        "| Output samples | API run ready median (ms) | Engine median (ms) | Retrieval median (ms) | Response bytes | Peak RSS (MiB) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["ramp"]:

        def med(entry: dict[str, Any]) -> str:
            return f"{entry['median'] * 1e3:.1f}" if entry.get("count") else "n/a"

        lines.append(
            f"| {item['output_samples']} | {med(item['api_run_ready_s'])} | {med(item['engine_wall_s'])} | "
            f"{med(item['series_retrieval_and_decode_s'])} | {item['response_bytes']} | "
            f"{(item['peak_sampled_app_rss_bytes'] or 0) / 2**20:.0f} |"
        )
    stress_report = report["stress"]
    lines += [
        "",
        "## Concurrent submissions",
        "",
        f"{stress_report['clients']} clients submit simultaneously, {len(stress_report['rounds'])} rounds: "
        + "; ".join(
            f"{item['accepted']} accepted / {item['busy_rejections']} busy, run {item['run_state']}, "
            f"health p95 during run {ms(item['health_latency_during_run_s'])} ms"
            for item in stress_report["rounds"]
        )
        + f". Verdict: {'PASS' if stress_report['passed'] else 'FAIL'}.",
        "",
        "## Resilience scenarios (software faults)",
        "",
        "| Scenario | Verdict | Checks |",
        "| :--- | :--- | :--- |",
    ]
    for name, result in report["resilience"].items():
        checks = result.get("checks", {})
        failed = [
            key
            for key, value in checks.items()
            if not (value["passed"] if isinstance(value, dict) else value)
        ]
        detail = "all passed" if not failed else "failed: " + ", ".join(failed)
        lines.append(
            f"| `{name}` | {'PASS' if result['passed'] else 'FAIL'} | {len(checks)} checks, {detail} |"
        )
    lines += ["", "## Limitations", ""] + [f"- {item}" for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--label", required=True, help="Machine profile label from the register")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSON report; a .md summary is written next to it",
    )
    parser.add_argument("--quick", action="store_true", help="Reduced development-cycle scenario")
    args = parser.parse_args()
    warmups, attempts = (1, 3) if args.quick else (3, 30)
    sizes = [(2, 360), (50, 720)] if args.quick else [(2, 360), (50, 720), (100, 3600), (277, 3600)]
    repetitions = 1 if args.quick else 3
    clients, rounds = (4, 1) if args.quick else (8, 3)
    started = now_utc()
    with tempfile.TemporaryDirectory(prefix="vtwin-bench-") as scratch:
        work = Path(scratch)
        sampler = GroupSampler()
        sampler.start()
        try:
            with running(Server(work / "nominal", sampler=sampler)) as server:
                time.sleep(1.0)  # idle samples before the first submission
                nominal_report = nominal(server, warmups, attempts)
                ramp_report = ramp(server, sizes, repetitions)
                stress_report = stress(server, clients, rounds, polls=50)
        finally:
            sampler.stop()
        resilience = {name: scenario(work) for name, scenario in SCENARIOS.items()}
    report = {
        "record_type": "runner_api_benchmark",
        "schema_version": "1.0.0",
        "protocol_version": PROTOCOL_VERSION,
        "captured_at_utc": started,
        "quick": args.quick,
        "product_baseline": False,
        "path_measured": "HTTP API on loopback (Python client → coordinator → spawned worker → paginated JSON series), no browser",
        "command": " ".join(["python", "scripts/benchmark_runner.py", *sys.argv[1:]]),
        "environment": environment(args.label),
        "python_executable_version": platform.python_version(),
        "clock": "time.perf_counter in the client process; engine spans from the worker's perf_counter_ns",
        "memory_sampling": {
            "interval_s": SAMPLE_INTERVAL_S,
            "group": "vtwin serve process and all descendants (spawned workers)",
            "samples": len(sampler.samples),
            "collection_errors": sampler.errors,
            "browser_group": None,
        },
        "product_kpis": {
            "run_ready_s": None,
            "run_ready_s_reason": "No browser/chart rendering in this campaign; see api_run_ready_s",
            "simulation_rate_aggregate_s_per_s": nominal_report["summary"][
                "simulation_rate_aggregate_s_per_s"
            ],
            "peak_sampled_app_rss_bytes_without_browser": nominal_report["summary"][
                "peak_sampled_app_rss_bytes"
            ],
        },
        "nominal": nominal_report,
        "ramp": ramp_report,
        "stress": stress_report,
        "resilience": resilience,
        "fault_classes": {
            "software": sorted(SCENARIOS),
            "simulated_physical_defects": [],
            "note": "Physical defect scenarios (SCN-004/005) need the tribology model and are not part of this bench.",
        },
        "limitations": [
            "Kinematic demo case only; not the SCN-001 tribological nominal workload of #39",
            "No browser: the < 60 s run_ready_s and < 1 s stored-result KPIs are only bounded by their API parts",
            "One machine and one campaign; no pooling across machines, no CI timing threshold",
            "RSS is sampled every 50 ms and summed over processes; short spikes can be missed and shared pages double-counted",
            "Each run spawns a fresh worker, so process start-up is inside every nominal attempt",
        ],
    }
    report["passed"] = (
        all(item["outcome"] == "completed" for item in nominal_report["attempts"])
        and stress_report["passed"]
        and all(item["passed"] for item in resilience.values())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {"passed": report["passed"], "nominal": nominal_report["summary"]["api_run_ready_s"]}
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
