"""Verify the measurement report does not invent product measurements."""

import json
import subprocess
import sys
from pathlib import Path


def test_probe_preserves_raw_attempts_and_marks_product_kpis_unmeasured(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "probe.json"
    subprocess.run(
        [sys.executable, str(root / "scripts/measure_foundation.py"), "--output", str(output)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["product_baseline"] is False
    assert len(report["attempts"]) == 30
    assert report["summary"]["correct_attempts"] == 30
    assert all(value is None for value in report["product_kpis"].values())
    durations = sorted(attempt["wall_s"] for attempt in report["attempts"])
    assert report["summary"]["p95_wall_s"] == durations[28]
    assert all(attempt["wall_s"] > 0 for attempt in report["attempts"])
