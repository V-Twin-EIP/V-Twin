"""Exercise the inventory entrypoint on the actual CI operating system."""

import json
import subprocess
import sys
from pathlib import Path


def test_inventory_keeps_missing_context_explicit(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "inventory.json"
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/performance_inventory.py"),
            "--label",
            "test-environment",
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["hardware"]["physical_memory_bytes"] > 0
    assert report["software"]["python"] == ".".join(map(str, sys.version_info[:3]))
    assert report["manual_context"]["browser_version"] is None
    assert report["manual_context"]["power_mode"] is None
    assert report["performance_measurements"] is None
    assert report["reference_machine_qualified"] is False
    assert "hostname" not in report["hardware"]
    assert len(report["source"]["lockfiles_sha256"]["uv.lock"]) == 64
