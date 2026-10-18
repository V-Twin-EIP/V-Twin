"""An analytical reference check, explicitly unrelated to engine wear validation."""

from dataclasses import dataclass

import numpy as np

from vtwin.domain.numerics import FloatArray, NumericalPolicy
from vtwin.ports.numerics import Integrator


@dataclass(frozen=True)
class NumericalCheck:
    check: str
    category: str
    passed: bool
    max_absolute_error: float
    acceptance_tolerance: float
    evaluations: int


def check_numerics(integrator: Integrator) -> NumericalCheck:
    """Check y'=-y, y(0)=1 against exp(-t), including the requested output grid."""

    def decay(_time_s: float, state: FloatArray) -> FloatArray:
        return -state

    times = np.linspace(0.0, 5.0, 51, dtype=np.float64)
    result = integrator.integrate(
        decay,
        np.array([1.0], dtype=np.float64),
        times,
        NumericalPolicy(relative_tolerance=1e-9, absolute_tolerance=1e-12),
    )
    error = float(np.max(np.abs(result.state[0] - np.exp(-times))))
    threshold = 1e-7  # Analytical smoke-check threshold, not a physical-model tolerance.
    return NumericalCheck(
        check="exponential_decay",
        category="analytical_reference",
        passed=error <= threshold,
        max_absolute_error=error,
        acceptance_tolerance=threshold,
        evaluations=result.evaluations,
    )
