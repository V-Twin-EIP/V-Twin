"""Portable developer commands; HTTP dependencies are imported only for serve.

Run and backup commands print one JSON document on stdout; logs go to stderr.
Exit codes: 0 success, 1 failed run or replay mismatch, 2 invalid input or
usage, 3 lifecycle conflict (busy, unknown run, wrong state), 4 storage or
integrity failure, 130 interrupted.
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


def _origin(value: str) -> str:
    """A development frontend origin; only explicit loopback HTTP origins are allowed."""
    from urllib.parse import urlsplit

    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"127.0.0.1", "localhost"}
        or parts.port is None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise argparse.ArgumentTypeError(
            "Allowed origins must look like http://localhost:5173 (loopback, explicit port)."
        )
    return f"http://{parts.hostname}:{parts.port}"


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Timeout must be a number of seconds.") from error
    if not 1 <= seconds <= 86_400:
        raise argparse.ArgumentTypeError("Timeout must be between 1 and 86400 seconds.")
    return seconds


def _data_dir(args: argparse.Namespace) -> Path:
    from vtwin.bootstrap import default_data_dir

    return Path(args.data_dir).expanduser().resolve() if args.data_dir else default_data_dir()


def _serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        import uvicorn

        from vtwin.adapters.http.app import SESSION_HEADER, RunApiSettings, create_app
    except ImportError:
        parser.error("The HTTP adapter requires the api extra: uv sync --locked --extra api")
    from vtwin.adapters.observability import configure_logging
    from vtwin.domain.errors import VTwinError

    web_dir = None if args.no_web else Path(args.web_dir).resolve()
    if web_dir is not None and not (web_dir / "index.html").is_file():
        parser.error("Build the UI first with npm --prefix web run build, or use --no-web.")
    try:
        origins = tuple(_origin(item) for item in args.allow_origin)
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))
    level, fmt = args.log_level or "INFO", args.log_format or "json"
    configure_logging(level, fmt)
    token = os.getenv("VTWIN_SESSION_TOKEN")
    try:
        settings = RunApiSettings(
            data_dir=_data_dir(args),
            port=args.port,
            dev_origins=origins,
            run_timeout_s=args.run_timeout_s,
            log_level=level,
            log_format=fmt,
            **({"session_token": token} if token else {}),
        )
        app = create_app(web_dir=web_dir, runs=settings)
    except VTwinError as error:
        print(f"vtwin serve: {error.code}: {error.message}", file=sys.stderr)
        return _exit_code(error)
    # The launch URL is the only place the token is shown; it is never logged or stored.
    print(
        f"V-Twin is ready: http://{args.host}:{args.port}/#session={settings.session_token}\n"
        f"Run API clients send the token in the {SESSION_HEADER} header. "
        f"Workspace: {settings.data_dir}",
        file=sys.stderr,
        flush=True,
    )
    uvicorn.run(
        app, host=args.host, port=args.port, log_config=None, access_log=False, server_header=False
    )
    return 0


def _backup_command(args: argparse.Namespace) -> int:
    from vtwin.adapters.storage.backup import create_backup, restore_backup
    from vtwin.adapters.storage.filesystem import FileRunStore, WorkspaceLock
    from vtwin.domain.errors import VTwinError

    data_dir = _data_dir(args)
    try:
        with WorkspaceLock(data_dir):
            store = FileRunStore(data_dir)
            if args.backup_command == "create":
                manifest = create_backup(store, Path(args.archive))
                _emit(
                    {
                        "ok": True,
                        "archive": str(Path(args.archive).resolve()),
                        "runs": len(manifest["runs"]),
                        "not_archived_staged_runs": manifest["not_archived_staged_runs"],
                    }
                )
            else:
                report = restore_backup(store, Path(args.archive))
                _emit({"ok": not report["conflicts"], **report})
                return 3 if report["conflicts"] else 0
    except VTwinError as error:
        _emit({"ok": False, "error": error.to_dict()})
        print(f"vtwin backup: {error.code}: {error.message}", file=sys.stderr)
        return _exit_code(error)
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
    from vtwin.adapters.observability import configure_logging
    from vtwin.adapters.storage.filesystem import WorkspaceLock
    from vtwin.bootstrap import create_run_service
    from vtwin.domain.errors import InvalidInput, VTwinError

    configure_logging(args.log_level or "WARNING", args.log_format or "text")
    data_dir = _data_dir(args)
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
    from vtwin.domain.errors import RunStateConflict, StorageFailure, VTwinError

    data_dir = _data_dir(args)
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
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.getenv("VTWIN_LOG_LEVEL"),
        help="Default: INFO for serve, WARNING for other commands",
    )
    parser.add_argument(
        "--log-format",
        choices=["json", "text"],
        default=os.getenv("VTWIN_LOG_FORMAT"),
        help="Structured logs on stderr. Default: json for serve, text otherwise",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "check-numerics", help="Check an analytical ODE, independent of engine models"
    )
    data_help = "Workspace directory (default: VTWIN_DATA_DIR or a per-user data directory)"
    serve = commands.add_parser("serve", help="Serve the local API and optional built frontend")
    serve.add_argument("--host", type=_host, default=os.getenv("VTWIN_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=_port, default=os.getenv("VTWIN_PORT", "8000"))
    serve.add_argument("--web-dir", default="web/dist")
    serve.add_argument("--no-web", action="store_true", help="API only, for the Vite dev server")
    serve.add_argument(
        "--allow-origin",
        action="append",
        default=[item for item in os.getenv("VTWIN_ALLOWED_ORIGINS", "").split(",") if item],
        help="Extra loopback dev-frontend origin allowed to call the run API (repeatable)",
    )
    serve.add_argument(
        "--run-timeout-s",
        type=_positive_seconds,
        default=os.getenv("VTWIN_RUN_TIMEOUT_S", "120"),
        help="Wall-clock limit of one worker execution (default 120)",
    )

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
    backup = commands.add_parser("backup", help="Back up or restore published runs")
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    backup_commands.add_parser("create", help="Archive published runs").add_argument("archive")
    backup_commands.add_parser("restore", help="Verify and restore runs").add_argument("archive")
    for name in ("serve", "run", "resume", "replay", "show", "export"):
        commands.choices[name].add_argument("--data-dir", help=data_help)
    for name in ("create", "restore"):
        backup_commands.choices[name].add_argument("--data-dir", help=data_help)

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args, parser)
    if args.command in {"run", "resume", "replay", "show"}:
        return _run_command(args)
    if args.command == "export":
        return _export_command(args)
    if args.command == "backup":
        return _backup_command(args)
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
