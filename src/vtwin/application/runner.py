"""Headless run use cases shared by the CLI and the HTTP coordinator.

Lifecycle: ``prepare`` validates and freezes a case (queued), ``compute`` advances
committed checkpoints in a staging area (running), ``publish`` verifies and
exposes immutable artifacts (completed). ``resume`` continues from the last
checkpoint; ``replay`` re-executes frozen inputs and compares with stored series.
"""

import hashlib
import json
import logging
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from vtwin.application.cases import canonical_json, decode_case, parse_case
from vtwin.domain.errors import (
    IntegrityFailure,
    NumericalFailure,
    RunInterrupted,
    RunStateConflict,
    UnsupportedModel,
    VTwinError,
)
from vtwin.domain.kinematics import OBSERVABLE_IDS, OBSERVABLES, KinematicCase
from vtwin.domain.numerics import FloatArray
from vtwin.domain.runs import Checkpoint, RunRecord, RunState
from vtwin.ports.engine import KinematicsEngine
from vtwin.ports.runs import RunStore

logger = logging.getLogger("vtwin.runs")

MANIFEST_SCHEMA_VERSION = "1.0.0"
REPLAY_RELATIVE_TOLERANCE = 1e-12
"""Numerical reproducibility tolerance, scaled by each observable's range.

Same build and platform are expected to be bit-identical (reported separately);
the tolerance absorbs last-bit libm differences between platforms. It is not a
physical accuracy tolerance: those belong to the validation protocol (#4).
"""


def _utc(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime) -> str:
    return f"run-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


@dataclass(frozen=True)
class ReplayReport:
    run_id: str
    identical: bool
    within_tolerance: bool
    samples: int
    observables: dict[str, dict[str, float]]
    relative_tolerance: float = REPLAY_RELATIVE_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "replay_report",
            "run_id": self.run_id,
            "identical": self.identical,
            "within_tolerance": self.within_tolerance,
            "samples": self.samples,
            "relative_tolerance": self.relative_tolerance,
            "tolerance_basis": "relative to max |value| per observable; not a physical tolerance",
            "observables": self.observables,
        }


@dataclass
class RunService:
    engine: KinematicsEngine
    store: RunStore
    software: Mapping[str, Any] = field(default_factory=dict)
    resource_probe: Callable[[], Mapping[str, Any]] = dict
    clock_ns: Callable[[], int] = time.perf_counter_ns
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    new_run_id: Callable[[datetime], str] = default_run_id

    # ----------------------------------------------------------------- events
    def _event(self, run_id: str, name: str, level: int = logging.INFO, **fields: Any) -> None:
        record = {"ts_utc": _utc(self.now()), "event": name, "run_id": run_id, **fields}
        self.store.append_event(run_id, record)
        logger.log(level, name, extra={"event": name, "run_id": run_id, **fields})

    def _save(self, record: RunRecord) -> None:
        self.store.write_status(record.run_id, record.to_dict())

    def status(self, run_id: str) -> RunRecord:
        return RunRecord.from_dict(self.store.read_status(run_id))

    # ---------------------------------------------------------------- prepare
    def prepare_bytes(self, raw: bytes) -> RunRecord:
        return self.prepare(decode_case(raw))

    def prepare(self, document: Mapping[str, Any]) -> RunRecord:
        case = parse_case(document)
        frozen = canonical_json(document)
        digest = hashlib.sha256(frozen).hexdigest()
        now = self.now()
        run_id = self.new_run_id(now)
        manifest = self._manifest(run_id, case, digest, now)
        self.store.create(run_id, frozen, manifest)
        record = RunRecord(
            run_id=run_id,
            case_id=case.case_id,
            state=RunState.QUEUED,
            created_at_utc=_utc(now),
            total_samples=case.total_samples,
        )
        self._save(record)
        self._event(run_id, "run_queued", case_id=case.case_id, case_sha256=digest)
        return record

    def _manifest(
        self, run_id: str, case: KinematicCase, digest: str, now: datetime
    ) -> dict[str, Any]:
        return {
            "record_type": "run_manifest",
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "run_id": run_id,
            "created_at_utc": _utc(now),
            "case": {
                "case_id": case.case_id,
                "title": case.title,
                "synthetic": case.synthetic,
                "file": "case.json",
                "sha256": digest,
                "provenance": dict(case.provenance),
            },
            "resolved_inputs_si": {
                "bore_m": case.bore_m,
                "stroke_m": case.stroke_m,
                "crank_radius_m": case.crank_radius_m,
                "connecting_rod_length_m": case.connecting_rod_length_m,
                "crank_speed_rad_s": case.crank_speed_rad_s,
                "crank_speed_rpm": case.crank_speed_rpm,
                "revolutions": case.revolutions,
                "samples_per_revolution": case.samples_per_revolution,
                "swept_volume_m3": case.swept_volume_m3,
            },
            "model": {"id": self.engine.model_id, "version": self.engine.model_version},
            "numerical_policy": {
                "method": "closed_form",
                "precision": "binary64",
                "time_step_s": case.time_step_s,
                "angle_step_rad": case.angle_step_rad,
                "output_samples": case.total_samples,
                "simulated_duration_s": case.simulated_duration_s,
                "chunk_samples": case.samples_per_revolution,
                "seed": None,
                "seed_reason": "Deterministic model; no random input.",
            },
            "observables": [
                {"id": item.id, "unit": item.unit, "definition": item.definition}
                for item in OBSERVABLES
            ],
            "replay": {
                "relative_tolerance": REPLAY_RELATIVE_TOLERANCE,
                "basis": "Numerical reproducibility, not physical accuracy (#4).",
            },
            "software": dict(self.software),
        }

    # ---------------------------------------------------------------- compute
    def _frozen_case(self, run_id: str) -> tuple[KinematicCase, dict[str, Any]]:
        manifest = self.store.read_manifest(run_id)
        raw = self.store.read_case(run_id)
        if hashlib.sha256(raw).hexdigest() != manifest["case"]["sha256"]:
            raise IntegrityFailure(f"Frozen case of {run_id} does not match its manifest hash.")
        model = manifest["model"]
        if (model["id"], model["version"]) != (self.engine.model_id, self.engine.model_version):
            raise UnsupportedModel(
                f"{run_id} was produced by {model['id']}@{model['version']}; this build provides "
                f"{self.engine.model_id}@{self.engine.model_version}."
            )
        return parse_case(json.loads(raw)), manifest

    def _evaluate(self, case: KinematicCase, start: int, stop: int) -> dict[str, FloatArray]:
        arrays = self.engine.evaluate(case, start, stop)
        if set(arrays) != set(OBSERVABLE_IDS):
            raise NumericalFailure("Engine returned an unexpected observable set.")
        checked: dict[str, FloatArray] = {}
        for name in OBSERVABLE_IDS:
            values = np.asarray(arrays[name], dtype=np.float64)
            if values.shape != (stop - start,) or not np.all(np.isfinite(values)):
                raise NumericalFailure(
                    f"Observable {name} is non-finite or misshaped for samples [{start}, {stop})."
                )
            checked[name] = values
        return checked

    def compute(self, run_id: str) -> RunRecord:
        """Advance from the last committed checkpoint and stage the complete series."""
        record = self.status(run_id)
        if record.state is RunState.COMPLETED:
            raise RunStateConflict(f"{run_id} is already completed.")
        if record.state is RunState.FAILED and not record.resumable:
            raise RunStateConflict(f"{run_id} failed with a non-retryable error.")
        case, manifest = self._frozen_case(run_id)
        digest = manifest["case"]["sha256"]
        checkpoint = self.store.read_checkpoint(run_id) or Checkpoint(case_sha256=digest)
        if checkpoint.case_sha256 != digest:
            raise IntegrityFailure(f"Checkpoint of {run_id} belongs to another case.")
        resumed = checkpoint.next_index > 0 or record.attempts > 0
        record.state = RunState.RUNNING
        record.attempts += 1
        record.error = None
        record.started_at_utc = record.started_at_utc or _utc(self.now())
        record.completed_samples = checkpoint.next_index
        self._save(record)
        self._event(
            run_id,
            "run_resumed" if resumed else "run_started",
            from_index=checkpoint.next_index,
            attempt=record.attempts,
        )
        chunk = case.samples_per_revolution
        last = self.clock_ns()
        try:
            while checkpoint.next_index < case.total_samples:
                start = checkpoint.next_index
                stop = min(start + chunk, case.total_samples)
                before = self.clock_ns()
                arrays = self._evaluate(case, start, stop)
                engine_ns = self.clock_ns() - before
                ref = self.store.write_chunk(run_id, start, stop, arrays)
                now = self.clock_ns()
                checkpoint = Checkpoint(
                    case_sha256=digest,
                    next_index=stop,
                    chunks=(*checkpoint.chunks, ref),
                    engine_wall_ns=checkpoint.engine_wall_ns + engine_ns,
                    compute_wall_ns=checkpoint.compute_wall_ns + now - last,
                    segments=record.attempts,
                )
                last = now
                self.store.write_checkpoint(run_id, checkpoint)
            series = self.store.read_chunks(run_id, checkpoint.chunks)
            if any(values.shape != (case.total_samples,) for values in series.values()):
                raise IntegrityFailure("Committed chunks do not cover the case grid exactly once.")
            self.store.write_series(run_id, series)
            checkpoint = Checkpoint(
                case_sha256=digest,
                next_index=checkpoint.next_index,
                chunks=checkpoint.chunks,
                engine_wall_ns=checkpoint.engine_wall_ns,
                compute_wall_ns=checkpoint.compute_wall_ns + self.clock_ns() - last,
                segments=record.attempts,
            )
            self.store.write_checkpoint(run_id, checkpoint)
        except KeyboardInterrupt:
            self._stop(run_id, RunState.INTERRUPTED, RunInterrupted("Run interrupted by signal."))
            raise RunInterrupted(f"{run_id} interrupted; resume it to continue.") from None
        except VTwinError as error:
            self._stop(run_id, RunState.FAILED, error)
            raise
        except Exception as error:
            internal = VTwinError(f"Unexpected {type(error).__name__} during computation.")
            self._stop(run_id, RunState.FAILED, internal, level=logging.ERROR)
            raise
        record = self.status(run_id)
        record.completed_samples = case.total_samples
        record.extra["compute_resources"] = dict(self.resource_probe())
        self._save(record)
        self._event(run_id, "run_computed", samples=case.total_samples)
        return record

    def _stop(
        self, run_id: str, state: RunState, error: VTwinError, level: int = logging.WARNING
    ) -> None:
        record = self.status(run_id)
        checkpoint = self.store.read_checkpoint(run_id)
        record.state = state
        record.error = error.to_dict()
        record.finished_at_utc = _utc(self.now())
        record.completed_samples = checkpoint.next_index if checkpoint else 0
        self._save(record)
        self._event(
            run_id,
            f"run_{state.value}",
            level=level,
            error_code=error.code,
            error_message=error.message,
            committed_samples=record.completed_samples,
        )

    def mark_failed(self, run_id: str, error: VTwinError) -> RunRecord:
        """Record a failure observed outside the computation (e.g. a supervised worker)."""
        self._stop(run_id, RunState.FAILED, error)
        return self.status(run_id)

    def mark_interrupted(self, run_id: str, reason: str) -> RunRecord:
        self._stop(run_id, RunState.INTERRUPTED, RunInterrupted(reason))
        return self.status(run_id)

    # ---------------------------------------------------------------- publish
    def publish(self, run_id: str) -> RunRecord:
        record = self.status(run_id)
        checkpoint = self.store.read_checkpoint(run_id)
        if (
            record.state is not RunState.RUNNING
            or checkpoint is None
            or checkpoint.next_index != record.total_samples
        ):
            raise RunStateConflict(f"{run_id} has no complete computation to publish.")
        manifest = self.store.read_manifest(run_id)
        simulated = float(manifest["numerical_policy"]["simulated_duration_s"])
        engine_s = checkpoint.engine_wall_ns / 1e9
        record.state = RunState.COMPLETED
        record.finished_at_utc = _utc(self.now())
        record.kpis = {
            "simulated_duration_s": simulated,
            "engine_wall_s": engine_s,
            "simulation_rate_s_per_s": simulated / engine_s if engine_s > 0 else None,
            "compute_wall_s": checkpoint.compute_wall_ns / 1e9,
            "output_samples": record.total_samples,
            "compute_segments": checkpoint.segments,
            "resources": record.extra.pop("compute_resources", None) or dict(self.resource_probe()),
            "clock": "time.perf_counter_ns in the computing process",
        }
        self._save(record)
        inventory = self.store.publish(run_id)
        self._event(
            run_id,
            "run_completed",
            samples=record.total_samples,
            engine_wall_s=engine_s,
            files=len(inventory["files"]),
        )
        return self.status(run_id)

    def execute(self, run_id: str) -> RunRecord:
        self.compute(run_id)
        return self.publish(run_id)

    def run(self, document: Mapping[str, Any]) -> RunRecord:
        return self.execute(self.prepare(document).run_id)

    def resume(self, run_id: str) -> RunRecord:
        record = self.status(run_id)
        if record.state is RunState.COMPLETED:
            raise RunStateConflict(f"{run_id} is already completed; nothing to resume.")
        if record.state is RunState.FAILED and not record.resumable:
            raise RunStateConflict(f"{run_id} failed with a non-retryable error.")
        return self.execute(run_id)

    def requeue(self, run_id: str) -> RunRecord:
        """Accept a resume request: persist ``queued`` before a worker picks it up."""
        record = self.status(run_id)
        if not record.resumable:
            raise RunStateConflict(f"{run_id} is {record.state.value} and cannot be resumed.")
        record.state = RunState.QUEUED
        record.finished_at_utc = None
        self._save(record)
        self._event(run_id, "run_requeued", previous_error=(record.error or {}).get("code"))
        return record

    def reconcile(self) -> list[RunRecord]:
        """Mark staged runs left queued/running by a dead process as interrupted.

        Call only while holding exclusive workspace ownership. A staged run whose
        status is already ``completed`` lost its publication step: publish it again.
        """
        changed: list[RunRecord] = []
        for run_id in self.store.list_runs():
            if self.store.location(run_id) != "staging":
                continue
            record = self.status(run_id)
            if record.state in {RunState.QUEUED, RunState.RUNNING}:
                changed.append(self.mark_interrupted(run_id, "Process stopped before completion."))
            elif record.state is RunState.COMPLETED:
                self.store.publish(run_id)
                self._event(run_id, "run_publication_recovered")
                changed.append(self.status(run_id))
        return changed

    # ----------------------------------------------------------------- replay
    def replay(self, run_id: str) -> ReplayReport:
        record = self.status(run_id)
        if record.state is not RunState.COMPLETED:
            raise RunStateConflict(f"{run_id} is {record.state.value}; only completed runs replay.")
        case, _ = self._frozen_case(run_id)
        stored = self.store.read_series(run_id)
        fresh = self._evaluate(case, 0, case.total_samples)
        report: dict[str, dict[str, float]] = {}
        identical = True
        within = True
        for name in OBSERVABLE_IDS:
            difference = np.abs(fresh[name] - stored[name])
            scale = max(float(np.max(np.abs(stored[name]))), np.finfo(np.float64).tiny)
            limit = REPLAY_RELATIVE_TOLERANCE * scale
            max_diff = float(np.max(difference))
            identical &= bool(np.array_equal(fresh[name], stored[name]))
            within &= max_diff <= limit
            report[name] = {"max_abs_difference": max_diff, "absolute_limit": limit}
        self._event(run_id, "run_replayed", identical=identical, within_tolerance=within)
        return ReplayReport(run_id, identical, within, case.total_samples, report)
