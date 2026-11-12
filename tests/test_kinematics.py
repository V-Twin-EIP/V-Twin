"""Slider-crank outputs against independently derived kinematic references."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from vtwin.application.cases import parse_case
from vtwin.domain.kinematics import KinematicCase
from vtwin.engine.kinematics import SliderCrankKinematics

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "cases"


def load(name: str) -> KinematicCase:
    return parse_case(json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


@pytest.fixture
def reference() -> KinematicCase:
    return load("kinematics-ref-2000rpm.json")


@pytest.fixture
def variant() -> KinematicCase:
    return load("kinematics-var-4000rpm.json")


def full(case: KinematicCase) -> dict[str, np.ndarray]:
    return SliderCrankKinematics().evaluate(case, 0, case.total_samples)


def test_dead_centres_stroke_and_period(reference: KinematicCase) -> None:
    out = full(reference)
    per_rev = reference.samples_per_revolution
    bdc = per_rev // 2
    x = out["piston_displacement_m"]
    v = out["piston_velocity_m_s"]
    # TDC at theta = 0 and every revolution; BDC at theta = pi; stroke = 2r.
    assert x[0] == 0.0
    assert x[bdc] == pytest.approx(0.086, abs=1e-15)
    assert x[per_rev] == pytest.approx(0.0, abs=1e-15)
    assert np.max(x) == pytest.approx(reference.stroke_m, abs=1e-15)
    assert np.min(x) >= -1e-15
    assert v[0] == 0.0
    assert abs(v[bdc]) < 1e-12
    assert abs(v[per_rev]) < 1e-12
    # Period at constant speed: one revolution takes 60 / rpm seconds.
    assert out["time_s"][per_rev] == pytest.approx(60.0 / 2000.0, rel=1e-15)
    assert out["crank_angle_rad"][per_rev] == pytest.approx(2.0 * math.pi, rel=1e-15)
    np.testing.assert_allclose(x[:per_rev], x[per_rev : 2 * per_rev], rtol=0, atol=1e-15)


def test_displacement_matches_geometric_construction(reference: KinematicCase) -> None:
    """Pin position from the rod/crank triangle, written independently of the engine."""
    out = full(reference)
    theta = out["crank_angle_rad"]
    r = reference.crank_radius_m
    rod = reference.connecting_rod_length_m
    crank_pin_x = r * np.sin(theta)
    crank_pin_y = r * np.cos(theta)
    piston_pin_y = crank_pin_y + np.sqrt(rod**2 - crank_pin_x**2)
    expected = (r + rod) - piston_pin_y
    np.testing.assert_allclose(out["piston_displacement_m"], expected, rtol=0, atol=1e-15)


def test_velocity_matches_finite_difference_of_displacement(reference: KinematicCase) -> None:
    engine = SliderCrankKinematics()
    out = full(reference)
    # Central difference with a fine independent step around every output sample.
    h = 1e-7
    dt = h / reference.crank_speed_rad_s
    theta = out["crank_angle_rad"]
    r = reference.crank_radius_m
    rod = reference.connecting_rod_length_m

    def x(angle: np.ndarray) -> np.ndarray:
        return r * (1 - np.cos(angle)) + rod - np.sqrt(rod**2 - (r * np.sin(angle)) ** 2)

    numeric = (x(theta + h) - x(theta - h)) / (2 * dt)
    np.testing.assert_allclose(out["piston_velocity_m_s"], numeric, rtol=0, atol=1e-6)
    assert engine.model_version == "1.0.0"


def test_long_rod_limit_approaches_simple_harmonic_motion() -> None:
    document = json.loads((EXAMPLES / "kinematics-ref-2000rpm.json").read_text(encoding="utf-8"))
    document["geometry"]["stroke"]["value"] = 2.0
    document["geometry"]["connecting_rod_length"]["value"] = 2000.0
    case = parse_case(document)
    out = full(case)
    omega_r = case.crank_speed_rad_s * case.crank_radius_m
    harmonic = omega_r * np.sin(out["crank_angle_rad"])
    ratio = case.crank_radius_m / case.connecting_rod_length_m
    np.testing.assert_allclose(out["piston_velocity_m_s"], harmonic, rtol=0, atol=ratio * omega_r)


def test_variant_changes_only_speed_and_scales_time_and_velocity(
    reference: KinematicCase, variant: KinematicCase
) -> None:
    assert reference.stroke_m == variant.stroke_m
    assert reference.connecting_rod_length_m == variant.connecting_rod_length_m
    assert variant.crank_speed_rpm == pytest.approx(2 * reference.crank_speed_rpm)
    ref, var = full(reference), full(variant)
    np.testing.assert_array_equal(ref["crank_angle_rad"], var["crank_angle_rad"])
    np.testing.assert_array_equal(ref["piston_displacement_m"], var["piston_displacement_m"])
    np.testing.assert_allclose(var["time_s"], ref["time_s"] / 2, rtol=1e-15)
    np.testing.assert_allclose(
        var["piston_velocity_m_s"], 2 * ref["piston_velocity_m_s"], rtol=1e-14, atol=1e-15
    )


def test_chunked_evaluation_equals_single_evaluation(reference: KinematicCase) -> None:
    engine = SliderCrankKinematics()
    whole = full(reference)
    pieces = [
        engine.evaluate(reference, start, min(start + 97, 721)) for start in range(0, 721, 97)
    ]
    for name, values in whole.items():
        np.testing.assert_array_equal(np.concatenate([part[name] for part in pieces]), values)
