"""Engine boundary used by the run service; implementations live in ``vtwin.engine``."""

from typing import Protocol

from vtwin.domain.kinematics import KinematicCase
from vtwin.domain.numerics import FloatArray


class KinematicsEngine(Protocol):
    model_id: str
    model_version: str

    def evaluate(self, case: KinematicCase, start: int, stop: int) -> dict[str, FloatArray]:
        """Return every observable for sample indices ``start <= i < stop``.

        Each sample must depend only on the case and its index, so chunked,
        interrupted and resumed executions produce the same values.
        """
        ...
