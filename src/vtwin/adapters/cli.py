"""Portable developer commands; HTTP dependencies are imported only for serve."""

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

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
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args, parser)
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
