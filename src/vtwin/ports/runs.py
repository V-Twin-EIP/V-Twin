"""Result-store boundary: the run service never touches paths or file formats."""

from collections.abc import Sequence
from typing import Any, Literal, Protocol

from vtwin.domain.numerics import FloatArray
from vtwin.domain.runs import Checkpoint, ChunkRef

Location = Literal["staging", "published"]


class RunStore(Protocol):
    def create(self, run_id: str, case_bytes: bytes, manifest: dict[str, Any]) -> None:
        """Create a staging area holding the frozen case and manifest."""
        ...

    def location(self, run_id: str) -> Location:
        """Raise ``RunNotFound`` for unknown or malformed identifiers."""
        ...

    def read_case(self, run_id: str) -> bytes: ...

    def read_manifest(self, run_id: str) -> dict[str, Any]: ...

    def read_status(self, run_id: str) -> dict[str, Any]: ...

    def write_status(self, run_id: str, status: dict[str, Any]) -> None: ...

    def append_event(self, run_id: str, event: dict[str, Any]) -> None: ...

    def read_events(self, run_id: str) -> list[dict[str, Any]]: ...

    def read_checkpoint(self, run_id: str) -> Checkpoint | None: ...

    def write_chunk(
        self, run_id: str, start: int, stop: int, arrays: dict[str, FloatArray]
    ) -> ChunkRef:
        """Durably write a chunk; it only counts once a checkpoint references it."""
        ...

    def write_checkpoint(self, run_id: str, checkpoint: Checkpoint) -> None:
        """Atomically replace the checkpoint: the commit point of a chunk."""
        ...

    def read_chunks(self, run_id: str, chunks: Sequence[ChunkRef]) -> dict[str, FloatArray]:
        """Verify checksums and concatenate committed chunks in order."""
        ...

    def write_series(self, run_id: str, arrays: dict[str, FloatArray]) -> None: ...

    def read_series(
        self,
        run_id: str,
        observables: Sequence[str] | None = None,
        start: int = 0,
        stop: int | None = None,
    ) -> dict[str, FloatArray]: ...

    def publish(self, run_id: str) -> dict[str, Any]:
        """Verify, inventory and atomically publish a staged run; return the inventory."""
        ...

    def list_runs(self) -> list[str]: ...
