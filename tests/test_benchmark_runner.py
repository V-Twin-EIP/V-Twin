"""Reduced load/resilience bench in the development cycle: behavior, never timing gates."""

import json
import subprocess
import sys
from pathlib import Path


def test_quick_bench_records_raw_attempts_and_passes_resilience(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "bench.json"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/benchmark_runner.py"),
            "--quick",
            "--label",
            "test-environment",
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    failed = {name: item for name, item in report["resilience"].items() if not item["passed"]}
    assert result.returncode == 0, (failed, report["stress"], result.stderr[-2000:])
    assert report["product_baseline"] is False
    assert report["product_kpis"]["run_ready_s"] is None
    assert len(report["nominal"]["attempts"]) == 3
    assert all(item["correctness"]["correct"] for item in report["nominal"]["attempts"])
    assert all(item["api_run_ready_s"] > 0 for item in report["nominal"]["attempts"])
    assert report["fault_classes"]["simulated_physical_defects"] == []
    assert output.with_suffix(".md").read_text(encoding="utf-8").startswith("# Runner API")
