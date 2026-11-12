"""Composition root; application services never choose concrete adapters."""

import os
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from vtwin.adapters.storage.filesystem import FileRunStore
from vtwin.application.runner import RunService
from vtwin.engine.kinematics import SliderCrankKinematics
from vtwin.engine.numerics import ScipyIntegrator
from vtwin.ports.engine import KinematicsEngine
from vtwin.ports.numerics import Integrator


def create_integrator() -> Integrator:
    return ScipyIntegrator()


def create_engine() -> KinematicsEngine:
    from vtwin.bootstrap.faults import maybe_inject

    return maybe_inject(SliderCrankKinematics())


def default_data_dir() -> Path:
    """``VTWIN_DATA_DIR`` or a per-user directory outside the repository."""
    configured = os.getenv("VTWIN_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base / "vtwin").resolve()


def _source_commit() -> str | None:
    root = Path(__file__).resolve().parents[3]
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def software_versions() -> dict[str, Any]:
    return {
        "vtwin": version("vtwin"),
        "numpy": version("numpy"),
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "source_commit": _source_commit(),
    }


def peak_rss() -> dict[str, Any]:
    """Process-lifetime peak resident memory of the computing process."""
    try:
        import resource
    except ImportError:  # Windows: no getrusage; psutil is a development-only dependency.
        return {"peak_rss_bytes": None, "reason": "getrusage unavailable on this platform"}
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1 if sys.platform == "darwin" else 1024  # bytes on macOS, KiB on Linux
    return {"peak_rss_bytes": value * scale, "method": "getrusage(RUSAGE_SELF).ru_maxrss"}


def create_run_service(data_dir: Path, engine: KinematicsEngine | None = None) -> RunService:
    return RunService(
        engine=engine or create_engine(),
        store=FileRunStore(data_dir),
        software=software_versions(),
        resource_probe=peak_rss,
    )


def compute_in_worker(
    data_dir: str, run_id: str, log_level: str, log_format: str, session: str
) -> None:
    """Child-process entrypoint: compute one staged run; the coordinator publishes it.

    Expected failures are already recorded in the run status by the service, so
    they only set a distinct exit code here.
    """
    import multiprocessing
    import threading

    from vtwin.adapters.observability import configure_logging, run_id_var
    from vtwin.domain.errors import VTwinError

    configure_logging(log_level, log_format, session=session)
    run_id_var.set(run_id)
    parent = multiprocessing.parent_process()
    if parent is not None:
        # An orphaned worker (coordinator killed) must not keep writing to the
        # staging area that the next coordinator reconciles as interrupted.
        def exit_with_parent() -> None:
            parent.join()
            os._exit(75)

        threading.Thread(target=exit_with_parent, name="parent-watchdog", daemon=True).start()
    try:
        create_run_service(Path(data_dir)).compute(run_id)
    except VTwinError:
        raise SystemExit(3) from None
