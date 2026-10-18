"""Numerical contract checks against independent analytical references."""

import numpy as np
import pytest

from vtwin.domain.numerics import (
    FloatArray,
    IntegrationFailure,
    InvalidNumericalInput,
    NumericalPolicy,
)
from vtwin.engine.numerics import ScipyIntegrator


def decay(_time: float, state: FloatArray) -> FloatArray:
    return -state


@pytest.mark.parametrize("method", ["RK45", "DOP853", "Radau", "BDF"])
def test_decay_matches_analytical_solution(method: str) -> None:
    times = np.linspace(0.0, 5.0, 101)
    policy = NumericalPolicy(1e-9, 1e-12, method=method)  # type: ignore[arg-type]
    result = ScipyIntegrator().integrate(decay, np.array([2.0]), times, policy)
    np.testing.assert_array_equal(result.time_s, times)
    np.testing.assert_allclose(result.state[0], 2.0 * np.exp(-times), rtol=2e-7, atol=1e-9)
    assert result.state.dtype == np.float64
    assert result.evaluations > 0
    assert not result.state.flags.writeable


def test_coupled_oscillator_preserves_solution_and_initial_input() -> None:
    def oscillator(_time: float, state: FloatArray) -> FloatArray:
        return np.array([state[1], -state[0]])

    initial = np.array([1.0, 0.0])
    times = np.linspace(0.0, 2 * np.pi, 129)
    result = ScipyIntegrator().integrate(
        oscillator, initial, times, NumericalPolicy(1e-10, 1e-12, max_step_s=0.05)
    )
    expected = np.vstack((np.cos(times), -np.sin(times)))
    np.testing.assert_allclose(result.state, expected, rtol=1e-7, atol=1e-9)
    np.testing.assert_array_equal(initial, [1.0, 0.0])


@pytest.mark.parametrize(
    "times",
    [[], [0.0], [0.0, 0.0], [1.0, 0.0], [0.0, np.nan], [0.0, np.inf], [[0.0, 1.0]]],
)
def test_invalid_output_grids_are_rejected(times: list[float]) -> None:
    with pytest.raises(InvalidNumericalInput):
        ScipyIntegrator().integrate(
            decay, np.array([1.0]), np.asarray(times), NumericalPolicy(1e-9, 1e-12)
        )


@pytest.mark.parametrize("initial", [[], [np.nan], [np.inf], [[1.0]]])
def test_invalid_states_are_rejected(initial: list[float]) -> None:
    with pytest.raises(InvalidNumericalInput):
        ScipyIntegrator().integrate(
            decay, np.asarray(initial), np.array([0.0, 1.0]), NumericalPolicy(1e-9, 1e-12)
        )


@pytest.mark.parametrize("value", [0.0, -1.0, np.nan, np.inf])
@pytest.mark.parametrize("field", ["relative_tolerance", "absolute_tolerance", "max_step_s"])
def test_invalid_policies_are_rejected(field: str, value: float) -> None:
    settings = {"relative_tolerance": 1e-9, "absolute_tolerance": 1e-12}
    settings[field] = value
    with pytest.raises(InvalidNumericalInput):
        ScipyIntegrator().integrate(
            decay, np.array([1.0]), np.array([0.0, 1.0]), NumericalPolicy(**settings)
        )


@pytest.mark.parametrize("output", [np.array([np.nan]), np.array([np.inf]), np.array([1.0, 2.0])])
def test_invalid_derivative_is_a_numerical_failure(output: FloatArray) -> None:
    def bad_derivative(_time: float, _state: FloatArray) -> FloatArray:
        return output

    with pytest.raises(IntegrationFailure, match="Derivative"):
        ScipyIntegrator().integrate(
            bad_derivative, np.array([1.0]), np.array([0.0, 1.0]), NumericalPolicy(1e-9, 1e-12)
        )


def test_singularity_does_not_publish_a_successful_partial_trajectory() -> None:
    def pole(time: float, _state: FloatArray) -> FloatArray:
        return np.array([1.0 / (1.0 - time)])

    with pytest.raises(IntegrationFailure):
        ScipyIntegrator().integrate(
            pole, np.array([0.0]), np.linspace(0.0, 2.0, 21), NumericalPolicy(1e-9, 1e-12)
        )
