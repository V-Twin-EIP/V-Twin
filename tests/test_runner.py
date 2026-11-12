"""Run lifecycle: provenance, determinism, interruption/resume and integrity checks."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vtwin.adapters.storage.filesystem import FileRunStore, WorkspaceLock
from vtwin.application.runner import RunService
from vtwin.bootstrap import create_run_service
from vtwin.domain.errors import (
    IntegrityFailure,
    NumericalFailure,
    RunInterrupted,
    RunNotFound,
    RunStateConflict,
    StorageFailure,
    WorkspaceBusy,
)
from vtwin.domain.kinematics import KinematicCase
from vtwin.domain.numerics import FloatArray
from vtwin.domain.runs import RunState
from vtwin.engine.kinematics import SliderCrankKinematics

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "cases"


@pytest.fixture
def document() -> dict[str, Any]:
    return json.loads((EXAMPLES / "kinematics-ref-2000rpm.json").read_text(encoding="utf-8"))


class FaultyEngine(SliderCrankKinematics):
    """Software fault injection: interrupt or corrupt one chunk, then behave normally."""

    def __init__(self, fail_at_start: int, fault: str) -> None:
        self.fail_at_start = fail_at_start
        self.fault = fault
        self.calls: list[tuple[int, int]] = []

    def evaluate(self, case: KinematicCase, start: int, stop: int) -> dict[str, FloatArray]:
        self.calls.append((start, stop))
        if start == self.fail_at_start and self.fault:
            fault, self.fault = self.fault, ""
            if fault == "interrupt":
                raise KeyboardInterrupt
            values = super().evaluate(case, start, stop)
            values["piston_velocity_m_s"][0] = np.nan
            return values
        return super().evaluate(case, start, stop)


def test_run_preserves_versions_configuration_and_step(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = create_run_service(tmp_path)
    record = service.run(document)
    assert record.state is RunState.COMPLETED
    manifest = service.store.read_manifest(record.run_id)
    assert manifest["model"] == {"id": "slider-crank-kinematics", "version": "1.0.0"}
    assert manifest["numerical_policy"]["time_step_s"] == pytest.approx(0.03 / 360)
    assert manifest["numerical_policy"]["seed"] is None
    assert manifest["software"]["vtwin"]
    assert len(manifest["case"]["sha256"]) == 64
    assert json.loads(service.store.read_case(record.run_id)) == document
    assert record.kpis is not None
    assert record.kpis["simulated_duration_s"] == pytest.approx(0.06)
    assert record.kpis["engine_wall_s"] > 0
    assert record.kpis["simulation_rate_s_per_s"] > 0
    events = [item["event"] for item in service.store.read_events(record.run_id)]
    assert events == ["run_queued", "run_started", "run_computed", "run_completed"]
    assert all(item["run_id"] == record.run_id for item in service.store.read_events(record.run_id))


def test_two_identical_runs_are_bit_identical_and_replay(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = create_run_service(tmp_path)
    first = service.run(document)
    second = service.run(document)
    assert first.run_id != second.run_id
    a = service.store.read_series(first.run_id)
    b = service.store.read_series(second.run_id)
    for name in a:
        np.testing.assert_array_equal(a[name], b[name])
    report = service.replay(first.run_id)
    assert report.identical and report.within_tolerance
    assert report.samples == 721


def test_interrupted_run_resumes_without_gap_or_double_counting(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    document["sampling"]["revolutions"] = 5
    reference = create_run_service(tmp_path / "reference").run(document)
    expected = FileRunStore(tmp_path / "reference").read_series(reference.run_id)

    engine = FaultyEngine(fail_at_start=720, fault="interrupt")
    store = FileRunStore(tmp_path / "work")
    service = RunService(engine=engine, store=store)
    queued = service.prepare(document)
    with pytest.raises(RunInterrupted):
        service.execute(queued.run_id)
    interrupted = service.status(queued.run_id)
    assert interrupted.state is RunState.INTERRUPTED
    assert interrupted.completed_samples == 720
    assert interrupted.resumable
    checkpoint = store.read_checkpoint(queued.run_id)
    assert checkpoint is not None and checkpoint.next_index == 720

    resumed = service.resume(queued.run_id)
    assert resumed.state is RunState.COMPLETED
    assert resumed.attempts == 2
    assert resumed.kpis is not None and resumed.kpis["compute_segments"] == 2
    assert engine.calls[:3] == [(0, 360), (360, 720), (720, 1080)]
    assert engine.calls[3] == (720, 1080)  # restarted at the committed index, not earlier
    series = store.read_series(queued.run_id)
    for name, values in expected.items():
        assert series[name].shape == (1801,)
        np.testing.assert_array_equal(series[name], values)
    events = [item["event"] for item in store.read_events(queued.run_id)]
    assert events == [
        "run_queued",
        "run_started",
        "run_interrupted",
        "run_resumed",
        "run_computed",
        "run_completed",
    ]


def test_uncommitted_chunk_is_recomputed_not_counted(
    tmp_path: Path, document: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStore(tmp_path)
    service = RunService(engine=SliderCrankKinematics(), store=store)
    run_id = service.prepare(document).run_id
    original = store.write_checkpoint
    calls = {"n": 0}

    def failing_commit(run: str, checkpoint: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:  # second chunk written to disk but never committed
            raise StorageFailure("Simulated disk failure during commit.")
        original(run, checkpoint)

    monkeypatch.setattr(store, "write_checkpoint", failing_commit)
    with pytest.raises(StorageFailure):
        service.execute(run_id)
    assert service.status(run_id).resumable
    monkeypatch.setattr(store, "write_checkpoint", original)
    assert service.resume(run_id).state is RunState.COMPLETED
    assert store.read_series(run_id)["time_s"].shape == (721,)


def test_numerical_failure_is_terminal_and_not_resumable(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = RunService(engine=FaultyEngine(360, "nan"), store=FileRunStore(tmp_path))
    run_id = service.prepare(document).run_id
    with pytest.raises(NumericalFailure):
        service.execute(run_id)
    record = service.status(run_id)
    assert record.state is RunState.FAILED
    assert record.error is not None and record.error["code"] == "numerical_failure"
    assert not record.resumable
    with pytest.raises(RunStateConflict):
        service.resume(run_id)
    assert service.store.location(run_id) == "staging"


def test_completed_run_cannot_be_resumed_and_unknown_ids_are_rejected(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = create_run_service(tmp_path)
    record = service.run(document)
    with pytest.raises(RunStateConflict):
        service.resume(record.run_id)
    for bad in ("run-20261112T000000Z-00000000", "../../etc/passwd", "run-x"):
        with pytest.raises(RunNotFound):
            service.status(bad)


def test_tampered_artifacts_are_detected(tmp_path: Path, document: dict[str, Any]) -> None:
    service = create_run_service(tmp_path)
    run_id = service.run(document).run_id
    base = tmp_path / "runs" / run_id
    series = base / "series.npz"
    data = bytearray(series.read_bytes())
    data[-40] ^= 0xFF
    series.write_bytes(bytes(data))
    with pytest.raises(IntegrityFailure):
        service.replay(run_id)
    case = base / "case.json"
    case.write_bytes(case.read_bytes().replace(b"2000", b"2001"))
    with pytest.raises(IntegrityFailure):
        service.replay(run_id)


def test_reconcile_marks_abandoned_runs_interrupted(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = create_run_service(tmp_path)
    run_id = service.prepare(document).run_id
    record = service.status(run_id)
    record.state = RunState.RUNNING
    service.store.write_status(run_id, record.to_dict())
    changed = service.reconcile()
    assert [item.run_id for item in changed] == [run_id]
    assert service.status(run_id).state is RunState.INTERRUPTED
    assert service.resume(run_id).state is RunState.COMPLETED


def test_workspace_has_a_single_owner(tmp_path: Path) -> None:
    with WorkspaceLock(tmp_path), pytest.raises(WorkspaceBusy):
        WorkspaceLock(tmp_path).acquire()
    with WorkspaceLock(tmp_path):
        pass


def test_completed_is_only_observable_once_artifacts_are_published(
    tmp_path: Path, document: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression found by the #46 bench: a poller saw "completed" before publication."""
    service = create_run_service(tmp_path)
    run_id = service.prepare(document).run_id
    original = service.store.publish
    seen: list[RunState] = []

    def observing_publish(run: str) -> dict[str, Any]:
        seen.append(service.status(run).state)
        return original(run)

    monkeypatch.setattr(service.store, "publish", observing_publish)
    assert service.execute(run_id).state is RunState.COMPLETED
    assert seen == [RunState.RUNNING]
    assert service.store.read_series(run_id)["time_s"].shape == (721,)


def test_reconcile_completes_a_run_stopped_after_publication(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    service = create_run_service(tmp_path)
    run_id = service.run(document).run_id
    record = service.status(run_id)
    record.state = RunState.RUNNING  # as if the process died before the final status write
    service.store.write_status(run_id, record.to_dict())
    assert [item.run_id for item in service.reconcile()] == [run_id]
    assert service.status(run_id).state is RunState.COMPLETED
    assert service.replay(run_id).identical
