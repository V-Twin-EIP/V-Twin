"""Launch the built local application on an available port and verify its HTTP surface.

Covers the public metadata routes and the protected run path end to end: a valid
case completes and its series are readable, an invalid case and a missing session
token are refused with structured errors.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request(
    url: str, *, token: str | None = None, body: bytes | None = None
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-VTwin-Session"] = token
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    data_dir = tempfile.mkdtemp(prefix="vtwin-smoke-")
    process = subprocess.Popen(
        [sys.executable, "-m", "vtwin", "serve", "--port", str(port), "--data-dir", data_dir],
        cwd=root,
        env={**os.environ, "VTWIN_SESSION_TOKEN": token},
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            if process.poll() is not None:
                raise RuntimeError("Local application exited before becoming ready.")
            try:
                with urllib.request.urlopen(base + "/health", timeout=1) as response:
                    assert json.load(response)["status"] == "ok"
                break
            except (OSError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Local application did not become ready.") from None
                time.sleep(0.1)
        with urllib.request.urlopen(base, timeout=5) as response:
            assert "<title>V-Twin</title>" in response.read().decode()
        status, capabilities = request(base + "/api/v1/capabilities")
        assert status == 200 and capabilities["simulation_available"] is True

        case = (root / "examples/cases/kinematics-ref-2000rpm.json").read_bytes()
        status, refused = request(base + "/api/v1/runs", body=case)
        assert status == 401 and refused["error"]["code"] == "unauthorized", refused
        invalid = case.replace(b'"unit": "rpm"', b'"unit": "Hz"')
        status, rejected = request(base + "/api/v1/runs", token=token, body=invalid)
        assert status == 422 and rejected["error"]["details"][0]["path"] == (
            "operating_point.crank_speed.unit"
        ), rejected

        status, accepted = request(base + "/api/v1/runs", token=token, body=case)
        assert status == 202, accepted
        run_id = accepted["run"]["run_id"]
        deadline = time.monotonic() + 60
        while True:
            _, run = request(f"{base}/api/v1/runs/{run_id}", token=token)
            if run["run"]["state"] in {"completed", "failed", "interrupted"}:
                break
            assert time.monotonic() < deadline, run
            time.sleep(0.05)
        assert run["run"]["state"] == "completed", run
        status, series = request(f"{base}/api/v1/runs/{run_id}/series?limit=1000", token=token)
        assert status == 200 and series["count"] == 721, series
        print("PASS: built UI, metadata, protected run submission, results and refusals.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
