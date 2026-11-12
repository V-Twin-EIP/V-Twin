"""Structured logs correlated by process session, HTTP request and run.

Every record carries ``session_id`` (random per process launch, not a secret),
plus ``request_id``/``run_id`` when known. Sensitive keys are dropped and any
registered secret value is masked in the rendered line, as defence in depth.
Request bodies, headers and case contents are never logged.
"""

import json
import logging
import secrets
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import IO, Any

_session = {"id": secrets.token_hex(6)}
request_id_var: ContextVar[str | None] = ContextVar("vtwin_request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("vtwin_run_id", default=None)

_SENSITIVE_KEYS = frozenset(
    {"authorization", "cookie", "password", "secret", "session_token", "token", "x-vtwin-session"}
)
_STANDARD = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}
_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Mask this exact value wherever it would appear in a rendered log line."""
    if value:
        _secrets.add(value)


def _mask(text: str) -> str:
    for value in _secrets:
        text = text.replace(value, "[REDACTED]")
    return text


def _fields(record: logging.LogRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ts_utc": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
        "session_id": _session["id"],
        "pid": record.process,
    }
    for name, value in (("request_id", request_id_var.get()), ("run_id", run_id_var.get())):
        if value:
            data[name] = value
    for key, value in record.__dict__.items():
        if key in _STANDARD or key.startswith("_"):
            continue
        data[key] = "[REDACTED]" if key.lower() in _SENSITIVE_KEYS else value
    if record.exc_info and record.exc_info[0] is not None:
        data["error_type"] = record.exc_info[0].__name__
        data["traceback"] = "".join(traceback.format_exception(*record.exc_info))
    return data


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return _mask(json.dumps(_fields(record), default=str, ensure_ascii=False))


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = _fields(record)
        head = f"{data.pop('ts_utc')} {data.pop('level'):<7} {data.pop('logger')}: "
        head += str(data.pop("message"))
        trace = data.pop("traceback", None)
        data.pop("pid")
        tail = " ".join(f"{key}={value}" for key, value in data.items())
        return _mask(f"{head} {tail}" + (f"\n{trace}" if trace else ""))


def session_id() -> str:
    return _session["id"]


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    stream: IO[str] | None = None,
    session: str | None = None,
) -> None:
    """Configure the ``vtwin`` logger tree once per process (CLI, server or worker).

    A spawned worker passes its coordinator's ``session`` to keep one correlation ID.
    """
    if session:
        _session["id"] = session
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root = logging.getLogger("vtwin")
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    root.propagate = False
