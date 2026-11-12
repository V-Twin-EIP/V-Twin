"""Resolved single-cylinder slider-crank case and its observable definitions (SI units)."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

CASE_SCHEMA = "vtwin.kinematic-case"
CASE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class Observable:
    id: str
    unit: str
    definition: str


OBSERVABLES: tuple[Observable, ...] = (
    Observable("time_s", "s", "Simulated time; t = 0 at crank angle 0 (top dead centre)."),
    Observable(
        "crank_angle_rad",
        "rad",
        "Crank angle from top dead centre in the direction of rotation, unwrapped.",
    ),
    Observable(
        "piston_displacement_m",
        "m",
        "Piston pin distance from its top-dead-centre position, positive towards the crank.",
    ),
    Observable(
        "piston_velocity_m_s",
        "m/s",
        "Time derivative of piston_displacement_m; positive while moving towards the crank.",
    ),
)
OBSERVABLE_IDS: tuple[str, ...] = tuple(item.id for item in OBSERVABLES)


@dataclass(frozen=True)
class KinematicCase:
    """A validated, unit-resolved case. Construct it through the case parser."""

    case_id: str
    title: str
    bore_m: float
    stroke_m: float
    connecting_rod_length_m: float
    crank_speed_rad_s: float
    revolutions: int
    samples_per_revolution: int
    synthetic: bool
    provenance: Mapping[str, str] = field(default_factory=dict)

    @property
    def crank_radius_m(self) -> float:
        return self.stroke_m / 2.0

    @property
    def crank_speed_rpm(self) -> float:
        return self.crank_speed_rad_s * 60.0 / (2.0 * math.pi)

    @property
    def angle_step_rad(self) -> float:
        return 2.0 * math.pi / self.samples_per_revolution

    @property
    def time_step_s(self) -> float:
        return self.angle_step_rad / self.crank_speed_rad_s

    @property
    def total_samples(self) -> int:
        """Output samples including both endpoints of the simulated interval."""
        return self.revolutions * self.samples_per_revolution + 1

    @property
    def simulated_duration_s(self) -> float:
        return (self.total_samples - 1) * self.time_step_s

    @property
    def swept_volume_m3(self) -> float:
        return math.pi / 4.0 * self.bore_m**2 * self.stroke_m
