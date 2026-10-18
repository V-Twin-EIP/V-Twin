"""Collect benchmark environment metadata, without claiming a performance result."""

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import psutil


def command_output(command: list[str], root: Path) -> str | None:
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def cpu_model(root: Path) -> str | None:
    if platform.system() == "Darwin":
        return command_output(["sysctl", "-n", "machdep.cpu.brand_string"], root) or None
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                name, separator, value = line.partition(":")
                if separator and name.strip() in {"model name", "Hardware"}:
                    return value.strip() or None
        except OSError:
            pass
    return platform.processor() or None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Non-identifying machine/profile label")
    parser.add_argument("--browser-name")
    parser.add_argument("--browser-version")
    parser.add_argument("--graphics", help="Reported graphics device; not a capability test")
    parser.add_argument("--output", type=Path, default=Path("artifacts/performance/inventory.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    git = shutil.which("git")
    status = (
        command_output([git, "status", "--porcelain", "--untracked-files=all"], root)
        if git
        else None
    )
    clock = time.get_clock_info("perf_counter")
    report = {
        "record_type": "environment_inventory",
        "schema_version": "1.0.0",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "machine_label": args.label,
        "hardware": {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "cpu_model": cpu_model(root),
            "logical_cpu_count": psutil.cpu_count(),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "physical_memory_bytes": psutil.virtual_memory().total,
        },
        "software": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "node": command_output([node, "--version"], root) if node else None,
            "packages": {
                name: package_version(name) for name in ("vtwin", "numpy", "scipy", "psutil")
            },
        },
        "source": {
            "commit": command_output([git, "rev-parse", "HEAD"], root) if git else None,
            "worktree_dirty": status != "" if status is not None else None,
            "lockfiles_sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ("uv.lock", "web/package-lock.json")
            },
        },
        "clock": {
            "name": "time.perf_counter_ns",
            "implementation": clock.implementation,
            "monotonic": clock.monotonic,
            "resolution_s": clock.resolution,
        },
        "manual_context": {
            "browser_name": args.browser_name,
            "browser_version": args.browser_version,
            "graphics_reported": args.graphics,
            "power_mode": None,
            "display_css_pixels": None,
            "device_pixel_ratio": None,
            "background_workload": None,
            "blas_backend_and_thread_count": None,
            "storage_medium_and_free_space": None,
        },
        "performance_measurements": None,
        "reference_machine_qualified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Inventory written to {args.output}; complete manual context before benchmarking.")


if __name__ == "__main__":
    main()
