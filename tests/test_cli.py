"""Exercise the installed entrypoint and its documented diagnostics."""

import json
import os
import subprocess
import sys

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
