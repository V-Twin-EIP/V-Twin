"""Measure the existing analytical check; never label it a product baseline."""

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import psutil

from vtwin.application.foundation import check_numerics
from vtwin.bootstrap import create_integrator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    integrator = create_integrator()
    for _ in range(3):
        if not check_numerics(integrator).passed:
            raise RuntimeError("Analytical correctness check failed during warm-up.")
    process = psutil.Process()
    attempts = []
    for index in range(30):
        start = time.perf_counter_ns()
        result = check_numerics(integrator)
        elapsed = (time.perf_counter_ns() - start) / 1e9
        attempts.append(
            {
                "attempt": index + 1,
                "wall_s": elapsed,
                "correct": result.passed,
                "max_absolute_error": result.max_absolute_error,
                "acceptance_tolerance": result.acceptance_tolerance,
                "evaluations": result.evaluations,
                "rss_after_bytes": process.memory_info().rss,
            }
        )
    durations = sorted(attempt["wall_s"] for attempt in attempts)
    source_files = [
        "src/vtwin/application/foundation.py",
        "src/vtwin/engine/numerics.py",
        "src/vtwin/domain/numerics.py",
        "src/vtwin/bootstrap/__init__.py",
        "scripts/measure_foundation.py",
        "uv.lock",
    ]
    report = {
        "record_type": "analytical_core_performance_probe",
        "schema_version": "1.0.0",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "product_baseline": False,
        "workload": {
            "id": "analytical-exponential-decay-v1",
            "equation": "y'=-y; y(0)=1; exact solution exp(-t)",
            "simulated_interval_s": [0, 5],
            "output_samples": 51,
            "method": "RK45",
            "relative_tolerance": 1e-9,
            "absolute_tolerance": 1e-12,
            "warmups": 3,
            "measured_attempts": 30,
        },
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "physical_memory_bytes": psutil.virtual_memory().total,
            "logical_cpus": psutil.cpu_count(),
            "python": platform.python_version(),
            "packages": {name: version(name) for name in ("numpy", "scipy", "psutil", "vtwin")},
        },
        "source": {
            "commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "files_sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in source_files
            },
        },
        "clock": "time.perf_counter_ns; one process; imports and warm-ups excluded",
        "attempts": attempts,
        "summary": {
            "correct_attempts": sum(bool(attempt["correct"]) for attempt in attempts),
            "median_wall_s": statistics.median(durations),
            "p95_wall_s": durations[math.ceil(0.95 * len(durations)) - 1],
            "minimum_wall_s": min(durations),
            "maximum_wall_s": max(durations),
            "maximum_observed_endpoint_rss_bytes": max(
                attempt["rss_after_bytes"] for attempt in attempts
            ),
        },
        "product_kpis": {
            "run_ready_s": None,
            "simulation_rate": None,
            "peak_sampled_app_rss_bytes": None,
        },
        "limitations": [
            "Analytical ODE only: no Hydra/contact/lubrication/wear model or SCN-001 execution",
            "No browser, queue, publication, result retrieval or rendering is measured",
            "RSS values are post-attempt observations, not sampled application peaks",
            "This establishes no product latency, physical accuracy or reference-PC qualification",
            "Hardware, BLAS, power and background load vary; do not pool different campaigns",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 0 if report["summary"]["correct_attempts"] == 30 else 1


if __name__ == "__main__":
    raise SystemExit(main())
