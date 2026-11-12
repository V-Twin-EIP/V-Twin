"""Expected failures, each with a stable code, recovery hint and retry semantics.

Adapters map these classes to HTTP statuses and CLI exit codes; the domain never
imports an adapter. Messages must stay safe to show and log: no secrets, host
paths outside the workspace or raw request bodies.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class FieldIssue:
    """One rejected input location, as a JSON-pointer-like dotted path."""

    path: str
    message: str


class VTwinError(Exception):
    """Base class for documented, expected application failures."""

    code: ClassVar[str] = "internal_error"
    retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, details: Sequence[FieldIssue] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.details = tuple(details)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": [{"path": item.path, "message": item.message} for item in self.details],
        }


class InvalidInput(VTwinError):
    """A request or configuration does not satisfy its schema, units or bounds."""

    code = "invalid_input"


class LimitExceeded(InvalidInput):
    """A valid-looking request exceeds a declared execution or output limit."""

    code = "limit_exceeded"


class UnsupportedModel(VTwinError):
    """The requested model, schema or version is not provided by this build."""

    code = "unsupported_model"


class RunNotFound(VTwinError):
    code = "run_not_found"


class RunStateConflict(VTwinError):
    """The operation is not valid in the run's current lifecycle state."""

    code = "run_state_conflict"


class WorkspaceBusy(VTwinError):
    """Another process or run owns the workspace; retry after it finishes."""

    code = "workspace_busy"
    retryable = True


class StorageFailure(VTwinError):
    code = "storage_failure"
    retryable = True


class IntegrityFailure(StorageFailure):
    """Persisted data is missing, inconsistent or fails checksum verification."""

    code = "integrity_failure"
    retryable = False


class NumericalFailure(VTwinError):
    """The model produced non-finite, misshaped or incomplete outputs."""

    code = "numerical_failure"


class RunInterrupted(VTwinError):
    """Execution stopped before completion; committed checkpoints are kept."""

    code = "run_interrupted"
    retryable = True


class WorkerFailure(VTwinError):
    """The supervised numerical process exited abnormally."""

    code = "worker_failure"
    retryable = True


class RunTimeout(WorkerFailure):
    code = "run_timeout"
