"""Run lifecycle and checkpoint records shared by the CLI, API and storage adapters."""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

RUN_ID_PATTERN = re.compile(r"^run-\d{8}T\d{6}Z-[0-9a-f]{8}$")
RUN_RECORD_SCHEMA_VERSION = "1.0.0"


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


TERMINAL_STATES = frozenset({RunState.COMPLETED, RunState.FAILED, RunState.INTERRUPTED})


@dataclass(frozen=True)
class ChunkRef:
    """A committed, checksummed block of samples ``start <= i < stop``."""

    start: int
    stop: int
    file: str
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "stop": self.stop, "file": self.file, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkRef":
        return cls(int(data["start"]), int(data["stop"]), str(data["file"]), str(data["sha256"]))


@dataclass(frozen=True)
class Checkpoint:
    """The resumable state of a run: everything before ``next_index`` is committed.

    The slider-crank model is algebraic in the sample index, so the sample index
    is the complete engine state. Stateful models will add their state vector here.
    """

    case_sha256: str
    next_index: int = 0
    chunks: tuple[ChunkRef, ...] = ()
    engine_wall_ns: int = 0
    compute_wall_ns: int = 0
    segments: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "run_checkpoint",
            "schema_version": "1.0.0",
            "case_sha256": self.case_sha256,
            "next_index": self.next_index,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "engine_wall_ns": self.engine_wall_ns,
            "compute_wall_ns": self.compute_wall_ns,
            "segments": self.segments,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            case_sha256=str(data["case_sha256"]),
            next_index=int(data["next_index"]),
            chunks=tuple(ChunkRef.from_dict(item) for item in data["chunks"]),
            engine_wall_ns=int(data["engine_wall_ns"]),
            compute_wall_ns=int(data["compute_wall_ns"]),
            segments=int(data["segments"]),
        )


@dataclass
class RunRecord:
    """Mutable lifecycle status persisted as ``status.json``."""

    run_id: str
    case_id: str
    state: RunState
    created_at_utc: str
    total_samples: int
    completed_samples: int = 0
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    attempts: int = 0
    error: dict[str, Any] | None = None
    kpis: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def resumable(self) -> bool:
        return self.state is RunState.INTERRUPTED or (
            self.state is RunState.FAILED and bool(self.error and self.error.get("retryable"))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "run_status",
            "schema_version": RUN_RECORD_SCHEMA_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "state": self.state.value,
            "created_at_utc": self.created_at_utc,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "attempts": self.attempts,
            "progress": {
                "completed_samples": self.completed_samples,
                "total_samples": self.total_samples,
            },
            "resumable": self.resumable,
            "error": self.error,
            "kpis": self.kpis,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        known = {
            "record_type",
            "schema_version",
            "run_id",
            "case_id",
            "state",
            "created_at_utc",
            "started_at_utc",
            "finished_at_utc",
            "attempts",
            "progress",
            "resumable",
            "error",
            "kpis",
        }
        return cls(
            run_id=str(data["run_id"]),
            case_id=str(data["case_id"]),
            state=RunState(data["state"]),
            created_at_utc=str(data["created_at_utc"]),
            total_samples=int(data["progress"]["total_samples"]),
            completed_samples=int(data["progress"]["completed_samples"]),
            started_at_utc=data.get("started_at_utc"),
            finished_at_utc=data.get("finished_at_utc"),
            attempts=int(data.get("attempts", 0)),
            error=data.get("error"),
            kpis=data.get("kpis"),
            extra={key: value for key, value in data.items() if key not in known},
        )
