"""Composition root; application services never choose concrete adapters."""

from vtwin.engine.numerics import ScipyIntegrator
from vtwin.ports.numerics import Integrator


def create_integrator() -> Integrator:
    return ScipyIntegrator()
