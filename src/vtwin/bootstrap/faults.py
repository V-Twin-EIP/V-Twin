"""Opt-in software fault injection for resilience tests and the #46 bench.

``VTWIN_FAULT_INJECTION`` takes comma-separated directives, for example
``delay_s=0.05,crash_at=720``. These simulate *software* faults (slow engine,
worker crash, non-finite output, hang); they are not simulated physical defects.
Never set this variable for real runs: it is logged as a warning when active.
"""

import logging
import os
import time
from dataclasses import dataclass

import numpy as np

from vtwin.domain.errors import InvalidInput
from vtwin.domain.kinematics import KinematicCase
from vtwin.domain.numerics import FloatArray
from vtwin.ports.engine import KinematicsEngine

logger = logging.getLogger("vtwin.faults")
ENV = "VTWIN_FAULT_INJECTION"


@dataclass(frozen=True)
class FaultPlan:
    delay_s: float = 0.0
    crash_at: int | None = None
    nan_at: int | None = None
    hang_at: int | None = None

    @classmethod
    def parse(cls, text: str) -> "FaultPlan":
        values: dict[str, float | int] = {}
        for item in filter(None, (part.strip() for part in text.split(","))):
            key, _, raw = item.partition("=")
            try:
                if key == "delay_s":
                    values[key] = float(raw)
                elif key in {"crash_at", "nan_at", "hang_at"}:
                    values[key] = int(raw)
                else:
                    raise ValueError
            except ValueError:
                raise InvalidInput(f"Invalid {ENV} directive {item!r}.") from None
        return cls(**values)  # type: ignore[arg-type]


class FaultInjectingEngine:
    def __init__(self, inner: KinematicsEngine, plan: FaultPlan) -> None:
        self.inner = inner
        self.plan = plan
        self.model_id = inner.model_id
        self.model_version = inner.model_version

    def evaluate(self, case: KinematicCase, start: int, stop: int) -> dict[str, FloatArray]:
        if self.plan.delay_s:
            time.sleep(self.plan.delay_s)
        if self.plan.crash_at is not None and start == self.plan.crash_at:
            logger.error("fault_injection_crash", extra={"event": "fault_injection_crash"})
            os._exit(70)
        if self.plan.hang_at is not None and start == self.plan.hang_at:
            time.sleep(3600)
        values = self.inner.evaluate(case, start, stop)
        if self.plan.nan_at is not None and start == self.plan.nan_at:
            values["piston_velocity_m_s"][0] = np.nan
        return values


def maybe_inject(engine: KinematicsEngine) -> KinematicsEngine:
    text = os.getenv(ENV, "").strip()
    if not text:
        return engine
    plan = FaultPlan.parse(text)
    logger.warning(
        "fault_injection_active", extra={"event": "fault_injection_active", "plan": repr(plan)}
    )
    return FaultInjectingEngine(engine, plan)
