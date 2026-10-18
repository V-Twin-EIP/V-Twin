"""Contracts for numerical integration, without HTTP or persistence types."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
Derivative = Callable[[float, FloatArray], FloatArray]


class InvalidNumericalInput(ValueError):
    """The initial state, output grid, or numerical policy is invalid."""


class IntegrationFailure(RuntimeError):
    """The numerical problem could not produce a complete finite trajectory."""


@dataclass(frozen=True)
class NumericalPolicy:
    """Explicit solver settings; tolerances are supplied by each caller."""

    relative_tolerance: float
    absolute_tolerance: float
    method: Literal["RK45", "DOP853", "Radau", "BDF"] = "RK45"
    max_step_s: float | None = None


@dataclass(frozen=True)
class Trajectory:
    """Binary64 values with shape (state count, sample count)."""

    time_s: FloatArray
    state: FloatArray
    evaluations: int
