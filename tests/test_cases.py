"""Case documents: unit conversion, provenance and precise rejection diagnostics."""

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from vtwin.application.cases import decode_case, parse_case
from vtwin.domain.errors import InvalidInput, LimitExceeded, UnsupportedModel

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/cases/kinematics-ref-2000rpm.json"


@pytest.fixture
def document() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def paths(error: InvalidInput) -> set[str]:
    return {issue.path for issue in error.details}


def test_example_resolves_to_si_with_provenance(document: dict[str, Any]) -> None:
    case = parse_case(document)
    assert case.stroke_m == pytest.approx(0.086)
    assert case.crank_speed_rad_s == pytest.approx(2000 * 2 * math.pi / 60)
    assert case.total_samples == 721
    assert case.synthetic is True
    assert "hypothèse de démo" in case.provenance["geometry.connecting_rod_length"]


def test_all_field_errors_are_reported_together(document: dict[str, Any]) -> None:
    broken = copy.deepcopy(document)
    broken["geometry"]["bore"]["unit"] = "inch"
    broken["geometry"]["stroke"]["value"] = "86"
    del broken["operating_point"]["crank_speed"]["source"]
    broken["sampling"]["revolutions"] = True
    broken["unexpected"] = 1
    with pytest.raises(InvalidInput) as caught:
        parse_case(broken)
    assert paths(caught.value) == {
        "geometry.bore.unit",
        "geometry.stroke.value",
        "operating_point.crank_speed.source",
        "sampling.revolutions",
        "unexpected",
    }
    assert caught.value.code == "invalid_input"


def test_rod_shorter_than_crank_radius_is_rejected(document: dict[str, Any]) -> None:
    document["geometry"]["connecting_rod_length"]["value"] = 43
    with pytest.raises(InvalidInput) as caught:
        parse_case(document)
    assert paths(caught.value) == {"geometry.connecting_rod_length"}


@pytest.mark.parametrize(("value", "unit"), [(0, "rpm"), (25_000, "rpm"), (-5, "rad/s")])
def test_speed_bounds(document: dict[str, Any], value: float, unit: str) -> None:
    document["operating_point"]["crank_speed"] = {"value": value, "unit": unit, "source": "test"}
    with pytest.raises(InvalidInput) as caught:
        parse_case(document)
    assert paths(caught.value) == {"operating_point.crank_speed.value"}


def test_output_volume_limit(document: dict[str, Any]) -> None:
    document["sampling"] = {"revolutions": 1000, "samples_per_revolution": 7200}
    with pytest.raises(LimitExceeded):
        parse_case(document)


def test_unknown_schema_version_and_model_are_unsupported(document: dict[str, Any]) -> None:
    with pytest.raises(UnsupportedModel):
        parse_case({**document, "schema_version": "2.0.0"})
    with pytest.raises(UnsupportedModel):
        parse_case({**document, "model": "hydra-wear"})


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a": NaN}',
        b'{"a": Infinity}',
        b'{"a": 1, "a": 2}',
        b"[1, 2]",
        b"\xff\xfe",
        b"{",
    ],
)
def test_strict_json_decoding(raw: bytes) -> None:
    with pytest.raises(InvalidInput):
        decode_case(raw)


def test_oversize_document_is_rejected_before_parsing() -> None:
    with pytest.raises(LimitExceeded):
        decode_case(b" " * (64 * 1024 + 1))
