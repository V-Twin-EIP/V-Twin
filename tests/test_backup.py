"""Backup/restore of published runs: verified round trip, refusal of corrupt archives."""

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from vtwin.adapters.storage.backup import create_backup, restore_backup
from vtwin.adapters.storage.filesystem import FileRunStore
from vtwin.bootstrap import create_run_service
from vtwin.domain.errors import IntegrityFailure, InvalidInput

CASE = Path(__file__).resolve().parents[1] / "examples/cases/kinematics-ref-2000rpm.json"


def vtwin(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vtwin", *args], capture_output=True, text=True, check=False
    )


def test_cli_backup_wipe_restore_and_replay(tmp_path: Path) -> None:
    data, archive = str(tmp_path / "data"), str(tmp_path / "backup.tar.gz")
    run_id = json.loads(vtwin("run", str(CASE), "--data-dir", data).stdout)["run"]["run_id"]
    created = vtwin("backup", "create", archive, "--data-dir", data)
    assert created.returncode == 0, created.stdout
    assert json.loads(created.stdout)["runs"] == 1

    fresh = str(tmp_path / "restored")
    restored = vtwin("backup", "restore", archive, "--data-dir", fresh)
    assert restored.returncode == 0, restored.stdout
    assert json.loads(restored.stdout)["restored"] == [run_id]
    replay = vtwin("replay", run_id, "--data-dir", fresh)
    assert replay.returncode == 0 and json.loads(replay.stdout)["identical"] is True

    again = json.loads(vtwin("backup", "restore", archive, "--data-dir", fresh).stdout)
    assert again["skipped_identical"] == [run_id] and again["restored"] == []


def test_staged_runs_are_reported_not_archived(tmp_path: Path) -> None:
    service = create_run_service(tmp_path / "data")
    staged = service.prepare(json.loads(CASE.read_text(encoding="utf-8"))).run_id
    manifest = create_backup(FileRunStore(tmp_path / "data"), tmp_path / "b.tar.gz")
    assert manifest["runs"] == [] and manifest["not_archived_staged_runs"] == [staged]
    with pytest.raises(InvalidInput):
        create_backup(FileRunStore(tmp_path / "data"), tmp_path / "data" / "inside.tar.gz")


def _rewrite(source: Path, target: Path, mutate: str) -> None:
    with tarfile.open(source, "r:gz") as old, tarfile.open(target, "w:gz") as new:
        for member in old.getmembers():
            handle = old.extractfile(member)
            assert handle is not None
            data = handle.read()
            if mutate == "corrupt" and member.name.endswith("series.npz"):
                data = data[:-1] + bytes([data[-1] ^ 1])
            if mutate == "traversal" and member.name.endswith("events.jsonl"):
                member.name = "../../evil.txt"
            member.size = len(data)
            new.addfile(member, io.BytesIO(data))


@pytest.mark.parametrize("mutate", ["corrupt", "traversal"])
def test_tampered_archives_are_refused_before_anything_is_restored(
    tmp_path: Path, mutate: str
) -> None:
    create_run_service(tmp_path / "data").run(json.loads(CASE.read_text(encoding="utf-8")))
    archive = tmp_path / "b.tar.gz"
    create_backup(FileRunStore(tmp_path / "data"), archive)
    bad = tmp_path / "bad.tar.gz"
    _rewrite(archive, bad, mutate)
    target = FileRunStore(tmp_path / "restored")
    with pytest.raises(IntegrityFailure):
        restore_backup(target, bad)
    assert target.list_runs() == []
    assert not (tmp_path / "evil.txt").exists()
    with pytest.raises(InvalidInput):
        restore_backup(target, tmp_path / "missing.tar.gz")
