"""Closed-form kinematics of a centred (zero pin offset) single-cylinder slider-crank.

Assumptions: rigid links, constant crank speed, no pin offset, no clearance.
With crank radius r, rod length l (l > r), angle theta from top dead centre:

    x(theta) = r (1 - cos theta) + l - sqrt(l^2 - r^2 sin^2 theta)
    v(theta) = omega r sin theta (1 + r cos theta / sqrt(l^2 - r^2 sin^2 theta))

Forces, torque, combustion, friction and wear are outside this model (#9 follow-up).
"""

import numpy as np

from vtwin.domain.errors import InvalidInput
from vtwin.domain.kinematics import KinematicCase
from vtwin.domain.numerics import FloatArray


class SliderCrankKinematics:
    model_id = "slider-crank-kinematics"
    model_version = "1.0.0"

    def evaluate(self, case: KinematicCase, start: int, stop: int) -> dict[str, FloatArray]:
        if not 0 <= start < stop <= case.total_samples:
            raise InvalidInput(f"Sample range [{start}, {stop}) is outside the case grid.")
        index = np.arange(start, stop, dtype=np.float64)
        theta = index * case.angle_step_rad
        time = index * case.time_step_s
        r = case.crank_radius_m
        rod = case.connecting_rod_length_m
        sin = np.sin(theta)
        cos = np.cos(theta)
        root = np.sqrt(rod * rod - (r * sin) ** 2)
        displacement = r * (1.0 - cos) + rod - root
        velocity = case.crank_speed_rad_s * r * sin * (1.0 + r * cos / root)
        return {
            "time_s": time,
            "crank_angle_rad": theta,
            "piston_displacement_m": displacement,
            "piston_velocity_m_s": velocity,
        }
