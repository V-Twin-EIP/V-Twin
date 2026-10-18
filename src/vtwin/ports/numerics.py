"""The numerical integration boundary used by application services."""

from typing import Protocol

from vtwin.domain.numerics import Derivative, FloatArray, NumericalPolicy, Trajectory


class Integrator(Protocol):
    def integrate(
        self,
        derivative: Derivative,
        initial_state: FloatArray,
        sample_times_s: FloatArray,
        policy: NumericalPolicy,
    ) -> Trajectory:
        """Return a complete trajectory or raise a documented domain error."""
        ...
