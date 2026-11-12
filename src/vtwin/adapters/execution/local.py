"""One coordinator, at most one supervised numerical child process (ADR 0003).

The coordinator persists a queued run before acknowledging it, spawns a worker
that computes into the staging area, supervises exit code and timeout, then
publishes verified artifacts itself. A second submission while a run is active
is rejected with ``workspace_busy`` (no hidden queue).
"""

import logging
import multiprocessing
import threading
from collections.abc import Callable
from pathlib import Path

from vtwin.adapters.observability import run_id_var, session_id
from vtwin.adapters.storage.filesystem import WorkspaceLock
from vtwin.application.runner import RunService
from vtwin.domain.errors import (
    RunTimeout,
    VTwinError,
    WorkerFailure,
    WorkspaceBusy,
)
from vtwin.domain.runs import RunRecord, RunState

logger = logging.getLogger("vtwin.execution")
WorkerTarget = Callable[[str, str, str, str, str], None]


class LocalCoordinator:
    def __init__(
        self,
        service: RunService,
        data_dir: Path,
        worker: WorkerTarget,
        *,
        timeout_s: float,
        log_level: str = "INFO",
        log_format: str = "json",
    ) -> None:
        self.service = service
        self.data_dir = data_dir
        self.worker = worker
        self.timeout_s = timeout_s
        self.log_level = log_level
        self.log_format = log_format
        self._mutex = threading.Lock()
        self._active: str | None = None
        self._thread: threading.Thread | None = None
        self._lock = WorkspaceLock(data_dir).acquire()
        recovered = service.reconcile()
        logger.info(
            "coordinator_started",
            extra={
                "event": "coordinator_started",
                "reconciled_runs": [record.run_id for record in recovered],
                "run_timeout_s": timeout_s,
            },
        )

    @property
    def active_run(self) -> str | None:
        return self._active

    def _claim(self) -> None:
        if self._active is not None:
            raise WorkspaceBusy(
                f"Run {self._active} is executing; one run at a time. Retry when it completes."
            )

    def submit(self, raw: bytes) -> RunRecord:
        with self._mutex:
            self._claim()
            record = self.service.prepare_bytes(raw)  # persisted as queued before the 202
            self._start(record.run_id)
        return record

    def resume(self, run_id: str) -> RunRecord:
        with self._mutex:
            self._claim()
            record = self.service.requeue(run_id)
            self._start(run_id)
        return record

    def _start(self, run_id: str) -> None:
        self._active = run_id
        self._thread = threading.Thread(
            target=self._supervise, args=(run_id,), name=f"supervise-{run_id}", daemon=True
        )
        self._thread.start()

    def _supervise(self, run_id: str) -> None:
        token = run_id_var.set(run_id)
        try:
            code = self._run_worker(run_id)
            # Finalize and release under the mutex: once a client can observe a
            # terminal state, a new submission is no longer refused as busy.
            with self._mutex:
                try:
                    self._finalize(run_id, code)
                finally:
                    self._active = None
        except Exception:
            logger.exception("supervision_crashed", extra={"event": "supervision_crashed"})
            with self._mutex:
                self._active = None
        finally:
            run_id_var.reset(token)

    def _run_worker(self, run_id: str) -> int | None:
        """Return the worker exit code, or ``None`` when it was stopped on timeout."""
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=self.worker,
            args=(str(self.data_dir), run_id, self.log_level, self.log_format, session_id()),
            name=f"vtwin-worker-{run_id}",
            daemon=True,
        )
        process.start()
        logger.info("worker_started", extra={"event": "worker_started", "worker_pid": process.pid})
        process.join(self.timeout_s)
        if not process.is_alive():
            return process.exitcode
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        return None

    def _finalize(self, run_id: str, code: int | None) -> None:
        try:
            if code is None:
                self.service.mark_failed(
                    run_id, RunTimeout(f"Worker exceeded the {self.timeout_s:g} s run timeout.")
                )
                state = RunState.FAILED
            else:
                state = self.service.status(run_id).state
                if code == 0 and state is RunState.RUNNING:
                    state = self.service.publish(run_id).state
                elif state in {RunState.QUEUED, RunState.RUNNING}:
                    error = WorkerFailure(f"Worker exited abnormally with code {code}.")
                    state = self.service.mark_failed(run_id, error).state
            logger.info(
                "worker_finished",
                extra={"event": "worker_finished", "exit_code": code, "state": state.value},
            )
        except VTwinError as error:
            logger.error(
                "supervision_failed",
                extra={"event": "supervision_failed", "error_code": error.code},
            )
            try:
                self.service.mark_failed(run_id, error)
            except VTwinError:
                logger.exception("status_update_failed", extra={"event": "status_update_failed"})

    def wait(self, timeout_s: float | None = None) -> None:
        """Wait for the active supervision thread (tests, orderly shutdown)."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout_s)

    def close(self, grace_s: float = 2.0) -> None:
        """Release ownership on shutdown after a short grace period.

        A worker still running then exits with its parent (watchdog) and the next
        coordinator reconciles the run as interrupted, resumable from its checkpoint.
        """
        self.wait(grace_s)
        self._lock.release()
