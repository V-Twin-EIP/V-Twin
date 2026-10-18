"""Run the Python quality gates and retain a reproducible machine-readable report."""

import json
import platform
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    reports = root / "artifacts"
    reports.mkdir(exist_ok=True)
    commands = [
        ("lint", [sys.executable, "-m", "ruff", "check", ".", "--output-format=json"]),
        ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
        ("types", [sys.executable, "-m", "mypy", "src"]),
        (
            "boundaries",
            [
                sys.executable,
                "-c",
                "from importlinter.cli import lint_imports_command; lint_imports_command()",
            ],
        ),
    ]
    results = []
    for name, command in commands:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
        results.append(
            {
                "name": name,
                "command": command[1:],
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}")
        if result.returncode:
            print(result.stdout or result.stderr)
    (reports / "python-quality.json").write_text(
        json.dumps(
            {
                "python": sys.version,
                "platform": platform.platform(),
                "architecture": platform.machine(),
                "checks": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return int(any(item["exit_code"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
