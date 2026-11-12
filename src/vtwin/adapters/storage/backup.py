"""Backup and restore of published runs, verified by checksum on both sides.

A backup requires exclusive workspace ownership (no server, no active CLI run),
so no run can be published while the archive is written. Staged, unfinished runs
are listed but not archived: they are not immutable and are resumed in place.
Restore verifies every file before moving a run into the workspace and never
overwrites an existing run.
"""

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from vtwin import __version__
from vtwin.adapters.storage.filesystem import FileRunStore
from vtwin.domain.errors import IntegrityFailure, InvalidInput, StorageFailure
from vtwin.domain.runs import RUN_ID_PATTERN

BACKUP_MANIFEST = "backup-manifest.json"
RUN_FILES = frozenset(
    {"case.json", "manifest.json", "series.npz", "inventory.json", "status.json", "events.jsonl"}
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_backup(store: FileRunStore, output: Path) -> dict[str, Any]:
    """Write a gzip tar archive of every published run; return the backup manifest."""
    output = output.resolve()
    if output.is_relative_to(store.data_dir.resolve()):
        raise InvalidInput("Write the backup outside the workspace directory.")
    runs: list[dict[str, Any]] = []
    staged: list[str] = []
    entries: list[tuple[str, bytes]] = []
    for run_id in store.list_runs():
        if store.location(run_id) != "published":
            staged.append(run_id)
            continue
        store.verify(run_id)
        base = store.runs_root / run_id
        files: dict[str, str] = {}
        for name in sorted(RUN_FILES):
            path = base / name
            if path.is_file():
                data = path.read_bytes()
                files[name] = _sha256(data)
                entries.append((f"runs/{run_id}/{name}", data))
        runs.append({"run_id": run_id, "files": files})
    manifest = {
        "record_type": "workspace_backup",
        "schema_version": "1.0.0",
        "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "vtwin_version": __version__,
        "runs": runs,
        "not_archived_staged_runs": staged,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with tarfile.open(temporary, "w:gz") as archive:
            for name, data in [
                (BACKUP_MANIFEST, json.dumps(manifest, indent=2).encode()),
                *entries,
            ]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(data))
        os.replace(temporary, output)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise StorageFailure(f"Could not write the backup: {error.strerror}.") from None
    return manifest


def _member_path(name: str) -> tuple[str, str] | None:
    parts = PurePosixPath(name).parts
    if name == BACKUP_MANIFEST:
        return None
    if (
        len(parts) != 3
        or parts[0] != "runs"
        or not RUN_ID_PATTERN.fullmatch(parts[1])
        or parts[2] not in RUN_FILES
    ):
        raise IntegrityFailure(f"Unexpected archive member {name[:120]!r}.")
    return parts[1], parts[2]


def restore_backup(store: FileRunStore, archive_path: Path) -> dict[str, Any]:
    """Verify and restore runs; existing identical runs are skipped, conflicts refused."""
    try:
        archive = tarfile.open(archive_path, "r:gz")  # noqa: SIM115 - closed by the with below
    except (OSError, tarfile.TarError):
        raise InvalidInput(f"Cannot open backup archive {archive_path.name}.") from None
    restored: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    with archive, tempfile.TemporaryDirectory(dir=store.data_dir, prefix=".restore-") as scratch:
        members = archive.getmembers()
        manifest: dict[str, Any] | None = None
        contents: dict[tuple[str, str], bytes] = {}
        for member in members:
            if not member.isfile():
                raise IntegrityFailure(f"Archive member {member.name[:120]!r} is not a file.")
            handle = archive.extractfile(member)
            assert handle is not None
            data = handle.read()
            key = _member_path(member.name)
            if key is None:
                manifest = json.loads(data)
            else:
                contents[key] = data
        if manifest is None or manifest.get("record_type") != "workspace_backup":
            raise IntegrityFailure("The archive has no V-Twin backup manifest.")
        listed = {(run["run_id"], name) for run in manifest["runs"] for name in run["files"]}
        if listed != set(contents):
            raise IntegrityFailure("Archive members do not match the backup manifest.")
        for run in manifest["runs"]:
            run_id = run["run_id"]
            for name, digest in run["files"].items():
                if _sha256(contents[(run_id, name)]) != digest:
                    raise IntegrityFailure(f"Checksum mismatch for {run_id}/{name} in the archive.")
            inventory = json.loads(contents[(run_id, "inventory.json")])
            for name, entry in inventory["files"].items():
                if _sha256(contents[(run_id, name)]) != entry["sha256"]:
                    raise IntegrityFailure(f"{run_id}/{name} does not match its run inventory.")
            target = store.runs_root / run_id
            if target.exists() or (store.staging_root / run_id).exists():
                same = (target / "inventory.json").is_file() and _sha256(
                    (target / "inventory.json").read_bytes()
                ) == run["files"]["inventory.json"]
                (skipped if same else conflicts).append(run_id)
                continue
            staging = Path(scratch) / run_id
            staging.mkdir(mode=0o700)
            for name in run["files"]:
                (staging / name).write_bytes(contents[(run_id, name)])
            shutil.move(staging, target)
            store.verify(run_id)
            restored.append(run_id)
    return {
        "record_type": "restore_report",
        "archive": archive_path.name,
        "restored": restored,
        "skipped_identical": skipped,
        "conflicts": conflicts,
    }
