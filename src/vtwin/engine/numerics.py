"""SciPy adapter with explicit input, callback and output validity checks."""

from typing import Protocol, cast

import numpy as np
from scipy.integrate import solve_ivp

from vtwin.domain.numerics import (
    Derivative,
    FloatArray,
    IntegrationFailure,
    InvalidNumericalInput,
    NumericalPolicy,
    Trajectory,
)


class _Solution(Protocol):
    success: bool
    message: str
    t: FloatArray
    y: FloatArray
    nfev: int


class ScipyIntegrator:
    """Integrate an ODE independently of web, storage and rendering adapters."""

    def integrate(
        self,
        derivative: Derivative,
        initial_state: FloatArray,
        sample_times_s: FloatArray,
        policy: NumericalPolicy,
    ) -> Trajectory:
        initial = np.array(initial_state, dtype=np.float64, copy=True)
        times = np.array(sample_times_s, dtype=np.float64, copy=True)
        if initial.ndim != 1 or initial.size == 0 or not np.all(np.isfinite(initial)):
            raise InvalidNumericalInput("Initial state must be a nonempty finite vector.")
        if times.ndim != 1 or times.size < 2 or not np.all(np.isfinite(times)):
            raise InvalidNumericalInput("Output times must contain at least two finite samples.")
        if not np.all(np.diff(times) > 0):
            raise InvalidNumericalInput("Output times must be strictly increasing.")
        for name, value in (
            ("relative_tolerance", policy.relative_tolerance),
            ("absolute_tolerance", policy.absolute_tolerance),
        ):
            if not np.isfinite(value) or value <= 0:
                raise InvalidNumericalInput(f"{name} must be finite and positive.")
        if policy.method not in {"RK45", "DOP853", "Radau", "BDF"}:
            raise InvalidNumericalInput("Unsupported integration method.")
        if policy.max_step_s is not None and (
            not np.isfinite(policy.max_step_s) or policy.max_step_s <= 0
        ):
            raise InvalidNumericalInput("max_step_s must be finite and positive when supplied.")

        def evaluate(time_s: float, state: FloatArray) -> FloatArray:
            try:
                values = np.asarray(derivative(time_s, state), dtype=np.float64)
            except (ValueError, TypeError, ArithmeticError) as error:
                raise IntegrationFailure("Derivative evaluation failed.") from error
            if values.shape != initial.shape or not np.all(np.isfinite(values)):
                raise IntegrationFailure("Derivative must match the state shape and be finite.")
            return values

        solution = cast(
            _Solution,
            solve_ivp(
                evaluate,
                (float(times[0]), float(times[-1])),
                initial,
                method=policy.method,
                t_eval=times,
                rtol=policy.relative_tolerance,
                atol=policy.absolute_tolerance,
                max_step=np.inf if policy.max_step_s is None else policy.max_step_s,
            ),
        )
        if not solution.success:
            raise IntegrationFailure(f"Integration failed: {solution.message}")
        values = np.asarray(solution.y, dtype=np.float64)
        output_times = np.asarray(solution.t, dtype=np.float64)
        if (
            values.shape != (initial.size, times.size)
            or not np.all(np.isfinite(values))
            or not np.array_equal(output_times, times)
        ):
            raise IntegrationFailure("Integration returned an incomplete or invalid trajectory.")
        output_times.setflags(write=False)
        values.setflags(write=False)
        return Trajectory(output_times, values, solution.nfev)
