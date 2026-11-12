"""Portable developer commands; HTTP dependencies are imported only for serve.

Run commands print one JSON document on stdout. Exit codes: 0 success, 1 failed
run or replay mismatch, 2 invalid input or usage, 3 lifecycle conflict (busy,
unknown run, wrong state), 4 storage or integrity failure, 130 interrupted.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vtwin import __version__


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be an integer.") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535.")
    return port


def _host(value: str) -> str:
    if value not in {"127.0.0.1", "localhost"}:
        raise argparse.ArgumentTypeError("Only loopback hosts are supported.")
    return value


def _serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        import uvicorn

        from vtwin.adapters.http.app import create_app
    except ImportError:
        parser.error("The HTTP adapter requires the api extra: uv sync --locked --extra api")
    web_dir = None if args.no_web else Path(args.web_dir).resolve()
    if web_dir is not None and not (web_dir / "index.html").is_file():
        parser.error("Build the UI first with npm --prefix web run build, or use --no-web.")
    uvicorn.run(create_app(web_dir=web_dir), host=args.host, port=args.port)
    return 0


def _emit(document: dict[str, Any]) -> None:
    print(json.dumps(document, indent=2, allow_nan=False, ensure_ascii=False))


def _exit_code(error: Exception) -> int:
    from vtwin.domain import errors

    if isinstance(error, errors.RunInterrupted):
        return 130
    if isinstance(error, errors.InvalidInput | errors.UnsupportedModel):
        return 2
    if isinstance(error, errors.RunNotFound | errors.RunStateConflict | errors.WorkspaceBusy):
        return 3
    if isinstance(error, errors.StorageFailure):
        return 4
    return 1


def _run_command(args: argparse.Namespace) -> int:
    from vtwin.adapters.storage.filesystem import WorkspaceLock
    from vtwin.bootstrap import create_run_service, default_data_dir
    from vtwin.domain.errors import InvalidInput, VTwinError

    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else default_data_dir()
    run_id: str | None = getattr(args, "run_id", None)
    try:
        service = create_run_service(data_dir)
        with WorkspaceLock(data_dir):
            service.reconcile()
            if args.command == "run":
                try:
                    raw = Path(args.case).read_bytes()
                except OSError as error:
                    raise InvalidInput(f"Cannot read case file: {error.strerror}.") from None
                prepared = service.prepare_bytes(raw)
                run_id = prepared.run_id
                record = service.execute(run_id)
            elif args.command == "resume":
                record = service.resume(args.run_id)
            elif args.command == "replay":
                report = service.replay(args.run_id)
                _emit(report.to_dict())
                return 0 if report.within_tolerance else 1
            else:  # show
                _emit(
                    {
                        "status": service.status(args.run_id).to_dict(),
                        "manifest": service.store.read_manifest(args.run_id),
                    }
                )
                return 0
    except VTwinError as error:
        _emit({"ok": False, "run_id": run_id, "error": error.to_dict()})
        print(f"vtwin {args.command}: {error.code}: {error.message}", file=sys.stderr)
        return _exit_code(error)
    _emit(
        {
            "ok": True,
            "run": record.to_dict(),
            "directory": str(data_dir / "runs" / record.run_id),
        }
    )
    return 0


def _export_command(args: argparse.Namespace) -> int:
    """Write a run's manifest and full series as one JSON file for offline import."""
    from vtwin.adapters.storage.filesystem import FileRunStore
    from vtwin.bootstrap import default_data_dir
    from vtwin.domain.errors import RunStateConflict, StorageFailure, VTwinError

    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else default_data_dir()
    try:
        store = FileRunStore(data_dir)
        if store.location(args.run_id) != "published":
            raise RunStateConflict(f"{args.run_id} is not completed.")
        manifest = store.read_manifest(args.run_id)
        series = store.read_series(args.run_id)
        document = {
            "record_type": "run_export",
            "schema_version": "1.0.0",
            "run_id": args.run_id,
            "status": store.read_status(args.run_id),
            "manifest": manifest,
            "series": {
                item["id"]: {"unit": item["unit"], "values": series[item["id"]].tolist()}
                for item in manifest["observables"]
            },
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(document, allow_nan=False) + "\n", encoding="utf-8")
    except VTwinError as error:
        _emit({"ok": False, "run_id": args.run_id, "error": error.to_dict()})
        return _exit_code(error)
    except OSError as error:
        failure = StorageFailure(f"Cannot write export: {error.strerror}.")
        _emit({"ok": False, "run_id": args.run_id, "error": failure.to_dict()})
        return 4
    _emit({"ok": True, "run_id": args.run_id, "output": str(output)})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vtwin", description="V-Twin developer foundation")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "check-numerics", help="Check an analytical ODE, independent of engine models"
    )
    serve = commands.add_parser("serve", help="Serve the local API and optional built frontend")
    serve.add_argument("--host", type=_host, default=os.getenv("VTWIN_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=_port, default=os.getenv("VTWIN_PORT", "8000"))
    serve.add_argument("--web-dir", default="web/dist")
    serve.add_argument("--no-web", action="store_true", help="API only, for the Vite dev server")

    data_help = "Workspace directory (default: VTWIN_DATA_DIR or a per-user data directory)"
    run = commands.add_parser("run", help="Validate, execute and publish a kinematic case file")
    run.add_argument("case", help="Case JSON file, e.g. examples/cases/kinematics-ref-2000rpm.json")
    for name, text in (
        ("resume", "Continue an interrupted or retryable failed run from its last checkpoint"),
        ("replay", "Re-execute a completed run's frozen inputs and compare with stored series"),
        ("show", "Print a run's status and manifest"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("run_id")
    export = commands.add_parser("export", help="Write a completed run as one JSON file")
    export.add_argument("run_id")
    export.add_argument("--output", required=True)
    for name in ("run", "resume", "replay", "show", "export"):
        commands.choices[name].add_argument("--data-dir", help=data_help)

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args, parser)
    if args.command in {"run", "resume", "replay", "show"}:
        return _run_command(args)
    if args.command == "export":
        return _export_command(args)
    from vtwin.application.foundation import check_numerics
    from vtwin.bootstrap import create_integrator
    from vtwin.domain.numerics import IntegrationFailure, InvalidNumericalInput

    try:
        result = check_numerics(create_integrator())
    except (InvalidNumericalInput, IntegrationFailure) as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 1
    print(json.dumps(asdict(result), allow_nan=False))
    return 0 if result.passed else 1
