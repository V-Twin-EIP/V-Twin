"""Workspace layout, atomic writes, checksums and exclusive ownership.

Layout under the data directory (created with owner-only permissions)::

    workspace.lock                  exclusive owner (CLI run or API coordinator)
    staging/<run_id>/               written while queued/running
        case.json manifest.json status.json events.jsonl
        checkpoint.json chunks/<start>.npz series.npz
    runs/<run_id>/                  published, immutable artifacts + lifecycle log
        case.json manifest.json series.npz inventory.json status.json events.jsonl

Publication is ``os.replace`` of the staging directory on the same filesystem,
after the artifact inventory and checksums are written and verified.
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Any

import numpy as np

from vtwin.domain.errors import IntegrityFailure, RunNotFound, StorageFailure, WorkspaceBusy
from vtwin.domain.kinematics import OBSERVABLE_IDS
from vtwin.domain.numerics import FloatArray
from vtwin.domain.runs import RUN_ID_PATTERN, Checkpoint, ChunkRef
from vtwin.ports.runs import Location

ARTIFACTS = ("case.json", "manifest.json", "series.npz")
MAX_SERIES_READ_SAMPLES = 1_000_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":  # Directory handles cannot be fsynced on Windows.
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace(source: Path, target: Path) -> None:
    """Rename over ``target``; on Windows, retry while a reader briefly holds a file open."""
    for attempt in range(40):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 39:
                raise
            time.sleep(0.05)


def atomic_write(path: Path, data: bytes) -> None:
    """Write via a sibling temporary file, fsync, then rename over the target."""
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _replace(temporary, path)


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False, ensure_ascii=False) + "\n").encode()


def _npz_bytes(arrays: dict[str, FloatArray]) -> bytes:
    """Uncompressed binary64 arrays, one per observable, without pickled objects."""
    buffer = io.BytesIO()
    named: dict[str, Any] = {
        key: np.asarray(arrays[key], dtype=np.float64) for key in OBSERVABLE_IDS
    }
    np.savez(buffer, **named)
    return buffer.getvalue()


@contextlib.contextmanager
def _storage_errors(action: str) -> Iterator[None]:
    try:
        yield
    except OSError as error:
        raise StorageFailure(
            f"Could not {action}: {error.strerror or type(error).__name__}."
        ) from None


class WorkspaceLock:
    """Non-blocking OS file lock; released automatically if the owner dies."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "workspace.lock"
        self._handle: IO[str] | None = None

    def acquire(self) -> "WorkspaceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = self.path.open("a+")
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise WorkspaceBusy(
                "The workspace is owned by another V-Twin process (a running server or CLI run). "
                "Submit through that server's API or wait for it to finish."
            ) from None
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "WorkspaceLock":
        return self.acquire()

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.release()


class FileRunStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.staging_root = data_dir / "staging"
        self.runs_root = data_dir / "runs"
        with _storage_errors("create the data directory"):
            for path in (data_dir, self.staging_root, self.runs_root):
                path.mkdir(parents=True, exist_ok=True, mode=0o700)

    # ---------------------------------------------------------------- paths
    def _checked_id(self, run_id: str) -> str:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise RunNotFound(f"Run {run_id[:80]!r} does not exist.")
        return run_id

    def location(self, run_id: str) -> Location:
        self._checked_id(run_id)
        if (self.runs_root / run_id).is_dir():
            return "published"
        if (self.staging_root / run_id).is_dir():
            return "staging"
        raise RunNotFound(f"Run {run_id} does not exist.")

    def _dir(self, run_id: str) -> Path:
        root = self.runs_root if self.location(run_id) == "published" else self.staging_root
        return root / run_id

    def _staging(self, run_id: str) -> Path:
        if self.location(run_id) != "staging":
            raise IntegrityFailure(f"Run {run_id} is published and immutable.")
        return self.staging_root / run_id

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return self._parse(path.read_bytes(), path.name, path.parent.name)
        except FileNotFoundError:
            raise IntegrityFailure(f"Missing {path.name} for run {path.parent.name}.") from None
        except OSError:
            raise IntegrityFailure(f"Unreadable {path.name} for run {path.parent.name}.") from None

    @staticmethod
    def _parse(data: bytes, name: str, run_id: str) -> dict[str, Any]:
        try:
            document = json.loads(data)
        except ValueError:
            raise IntegrityFailure(f"Unreadable {name} for run {run_id}.") from None
        if not isinstance(document, dict):
            raise IntegrityFailure(f"Malformed {name} for run {run_id}.")
        return document

    def _read_run_bytes(self, run_id: str, name: str) -> bytes:
        """Read a run file, re-resolving once if publication moved the directory meanwhile."""
        for attempt in range(2):
            path = self._dir(run_id) / name
            try:
                return path.read_bytes()
            except FileNotFoundError:
                moved = (
                    path.parent.parent == self.staging_root and (self.runs_root / run_id).is_dir()
                )
                if attempt == 0 and moved:
                    continue
                raise IntegrityFailure(f"Missing {name} for run {run_id}.") from None
            except OSError:
                raise IntegrityFailure(f"Unreadable {name} for run {run_id}.") from None
        raise IntegrityFailure(f"Missing {name} for run {run_id}.")

    def _read_run_json(self, run_id: str, name: str) -> dict[str, Any]:
        return self._parse(self._read_run_bytes(run_id, name), name, run_id)

    # ---------------------------------------------------------------- records
    def create(self, run_id: str, case_bytes: bytes, manifest: dict[str, Any]) -> None:
        self._checked_id(run_id)
        target = self.staging_root / run_id
        with _storage_errors("create the run staging area"):
            target.mkdir(mode=0o700)
            (target / "chunks").mkdir(mode=0o700)
            atomic_write(target / "case.json", case_bytes)
            atomic_write(target / "manifest.json", _json_bytes(manifest))

    def read_case(self, run_id: str) -> bytes:
        return self._read_run_bytes(run_id, "case.json")

    def read_manifest(self, run_id: str) -> dict[str, Any]:
        return self._read_run_json(run_id, "manifest.json")

    def read_status(self, run_id: str) -> dict[str, Any]:
        return self._read_run_json(run_id, "status.json")

    def write_status(self, run_id: str, status: dict[str, Any]) -> None:
        with _storage_errors("write the run status"):
            atomic_write(self._dir(run_id) / "status.json", _json_bytes(status))

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        line = json.dumps(event, allow_nan=False, ensure_ascii=False, default=str) + "\n"
        with (
            _storage_errors("append a run event"),
            (self._dir(run_id) / "events.jsonl").open("a", encoding="utf-8") as handle,
        ):
            handle.write(line)

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        try:
            text = self._read_run_bytes(run_id, "events.jsonl").decode("utf-8")
        except IntegrityFailure:
            return []
        return [json.loads(line) for line in text.splitlines() if line]

    # ------------------------------------------------------------ checkpoints
    def read_checkpoint(self, run_id: str) -> Checkpoint | None:
        path = self._dir(run_id) / "checkpoint.json"
        if not path.exists():
            return None
        try:
            return Checkpoint.from_dict(self._read_json(path))
        except (KeyError, TypeError, ValueError):
            raise IntegrityFailure(f"Malformed checkpoint for run {run_id}.") from None

    def write_chunk(
        self, run_id: str, start: int, stop: int, arrays: dict[str, FloatArray]
    ) -> ChunkRef:
        name = f"chunks/{start:09d}.npz"
        data = _npz_bytes(arrays)
        with _storage_errors("write a result chunk"):
            atomic_write(self._staging(run_id) / name, data)
        return ChunkRef(start, stop, name, hashlib.sha256(data).hexdigest())

    def write_checkpoint(self, run_id: str, checkpoint: Checkpoint) -> None:
        with _storage_errors("commit the checkpoint"):
            atomic_write(
                self._staging(run_id) / "checkpoint.json", _json_bytes(checkpoint.to_dict())
            )

    def _load_npz(self, path: Path, expected_sha256: str | None = None) -> dict[str, FloatArray]:
        try:
            data = path.read_bytes()
        except OSError:
            raise IntegrityFailure(f"Missing result file {path.name}.") from None
        if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise IntegrityFailure(f"Checksum mismatch for {path.name}.")
        try:
            with np.load(io.BytesIO(data), allow_pickle=False) as archive:
                return {key: np.asarray(archive[key], dtype=np.float64) for key in OBSERVABLE_IDS}
        except (OSError, KeyError, ValueError):
            raise IntegrityFailure(f"Unreadable result file {path.name}.") from None

    def read_chunks(self, run_id: str, chunks: Sequence[ChunkRef]) -> dict[str, FloatArray]:
        base = self._staging(run_id)
        expected = 0
        parts: dict[str, list[FloatArray]] = {key: [] for key in OBSERVABLE_IDS}
        for chunk in chunks:
            if chunk.start != expected or chunk.stop <= chunk.start:
                raise IntegrityFailure(f"Checkpoint chunks of {run_id} overlap or leave a gap.")
            arrays = self._load_npz(base / chunk.file, chunk.sha256)
            for key in OBSERVABLE_IDS:
                if arrays[key].shape != (chunk.stop - chunk.start,):
                    raise IntegrityFailure(f"Chunk {chunk.file} of {run_id} has a wrong length.")
                parts[key].append(arrays[key])
            expected = chunk.stop
        if not chunks:
            return {key: np.empty(0, dtype=np.float64) for key in OBSERVABLE_IDS}
        return {key: np.concatenate(values) for key, values in parts.items()}

    def write_series(self, run_id: str, arrays: dict[str, FloatArray]) -> None:
        with _storage_errors("write the result series"):
            atomic_write(self._staging(run_id) / "series.npz", _npz_bytes(arrays))

    def read_series(
        self,
        run_id: str,
        observables: Sequence[str] | None = None,
        start: int = 0,
        stop: int | None = None,
    ) -> dict[str, FloatArray]:
        if self.location(run_id) != "published":
            raise IntegrityFailure(f"Run {run_id} has no published series.")
        base = self.runs_root / run_id
        inventory = self._read_json(base / "inventory.json")
        arrays = self._load_npz(base / "series.npz", inventory["files"]["series.npz"]["sha256"])
        names = OBSERVABLE_IDS if observables is None else tuple(observables)
        selected = {name: arrays[name][start:stop] for name in names}
        return selected

    # ------------------------------------------------------------ publication
    def publish(self, run_id: str) -> dict[str, Any]:
        source = self._staging(run_id)
        files: dict[str, Any] = {}
        for name in ARTIFACTS:
            path = source / name
            if not path.is_file():
                raise IntegrityFailure(f"Cannot publish {run_id}: {name} is missing.")
            files[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        series = self._load_npz(source / "series.npz", files["series.npz"]["sha256"])
        manifest = self._read_json(source / "manifest.json")
        samples = int(manifest["numerical_policy"]["output_samples"])
        if any(values.shape != (samples,) for values in series.values()):
            raise IntegrityFailure(f"Cannot publish {run_id}: series length is not {samples}.")
        inventory = {"record_type": "artifact_inventory", "run_id": run_id, "files": files}
        with _storage_errors("publish the run"):
            atomic_write(source / "inventory.json", _json_bytes(inventory))
            shutil.rmtree(source / "chunks", ignore_errors=True)
            with contextlib.suppress(FileNotFoundError):
                (source / "checkpoint.json").unlink()
            _replace(source, self.runs_root / run_id)
            _fsync_dir(self.runs_root)
        return inventory

    def verify(self, run_id: str) -> dict[str, Any]:
        """Re-check a published run's inventory against its files."""
        if self.location(run_id) != "published":
            raise IntegrityFailure(f"Run {run_id} is not published.")
        base = self.runs_root / run_id
        inventory = self._read_json(base / "inventory.json")
        for name, entry in inventory["files"].items():
            path = base / name
            if not path.is_file() or sha256_file(path) != entry["sha256"]:
                raise IntegrityFailure(f"Run {run_id}: {name} is missing or modified.")
        return inventory

    def list_runs(self) -> list[str]:
        names: set[str] = set()
        for root in (self.staging_root, self.runs_root):
            with contextlib.suppress(FileNotFoundError):
                names.update(
                    entry.name
                    for entry in root.iterdir()
                    if entry.is_dir() and RUN_ID_PATTERN.fullmatch(entry.name)
                )
        return sorted(names)
