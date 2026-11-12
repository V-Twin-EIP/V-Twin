"""Exercise the installed entrypoint and its documented diagnostics."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_analytical_check_is_explicit_and_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vtwin", "check-numerics"],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert report["category"] == "analytical_reference"
    assert report["max_absolute_error"] < report["acceptance_tolerance"]


@pytest.mark.parametrize("value", ["0", "65536", "not-a-port"])
def test_invalid_port_is_diagnosed_before_starting_a_server(value: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vtwin", "serve", "--no-web", "--port", value],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Port must" in result.stderr


def test_environment_cannot_silently_expose_the_server() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vtwin", "serve", "--no-web"],
        env={**os.environ, "VTWIN_HOST": "0.0.0.0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Only loopback" in result.stderr


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples" / "cases" / "kinematics-ref-2000rpm.json"


def vtwin(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vtwin", *args], capture_output=True, text=True, check=False
    )


def test_run_replay_show_and_export_a_case(tmp_path: Path) -> None:
    data = str(tmp_path / "data")
    result = vtwin("run", str(CASE), "--data-dir", data)
    assert result.returncode == 0, result.stderr
    run = json.loads(result.stdout)["run"]
    assert run["state"] == "completed"
    assert run["progress"] == {"completed_samples": 721, "total_samples": 721}

    replay = vtwin("replay", run["run_id"], "--data-dir", data)
    assert replay.returncode == 0
    assert json.loads(replay.stdout)["identical"] is True

    shown = json.loads(vtwin("show", run["run_id"], "--data-dir", data).stdout)
    assert shown["manifest"]["case"]["case_id"] == "KIN-DEMO-REF"

    output = tmp_path / "export.json"
    assert (
        vtwin("export", run["run_id"], "--data-dir", data, "--output", str(output)).returncode == 0
    )
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert exported["series"]["piston_velocity_m_s"]["unit"] == "m/s"
    assert len(exported["series"]["time_s"]["values"]) == 721


def test_invalid_case_reports_field_paths_and_creates_no_run(tmp_path: Path) -> None:
    document = json.loads(CASE.read_text(encoding="utf-8"))
    document["geometry"]["stroke"]["unit"] = "inch"
    case = tmp_path / "bad.json"
    case.write_text(json.dumps(document), encoding="utf-8")
    result = vtwin("run", str(case), "--data-dir", str(tmp_path / "data"))
    assert result.returncode == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "invalid_input"
    assert error["details"] == [
        {"path": "geometry.stroke.unit", "message": "Must be one of: m, mm."}
    ]
    assert not any((tmp_path / "data" / "runs").iterdir())
    assert not any((tmp_path / "data" / "staging").iterdir())


def test_missing_case_file_and_unknown_run_are_diagnosed(tmp_path: Path) -> None:
    data = str(tmp_path / "data")
    assert vtwin("run", str(tmp_path / "missing.json"), "--data-dir", data).returncode == 2
    unknown = vtwin("replay", "run-20260101T000000Z-00000000", "--data-dir", data)
    assert unknown.returncode == 3
    assert json.loads(unknown.stdout)["error"]["code"] == "run_not_found"


def test_cli_refuses_a_workspace_owned_by_another_process(tmp_path: Path) -> None:
    from vtwin.adapters.storage.filesystem import WorkspaceLock

    with WorkspaceLock(tmp_path):
        result = vtwin("run", str(CASE), "--data-dir", str(tmp_path))
    assert result.returncode == 3
    assert json.loads(result.stdout)["error"]["code"] == "workspace_busy"
