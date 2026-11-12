"""Parse and validate kinematic case documents at the input boundary.

Every rejected field is reported at once with its path. Values are converted to
SI here; nothing downstream sees millimetres or RPM.
"""

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vtwin.domain.errors import FieldIssue, InvalidInput, LimitExceeded, UnsupportedModel
from vtwin.domain.kinematics import CASE_SCHEMA, CASE_SCHEMA_VERSION, KinematicCase

SUPPORTED_MODELS = frozenset({"slider-crank-kinematics"})
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_LENGTH_UNITS = {"m": 1.0, "mm": 1e-3}
_SPEED_UNITS = {"rpm": 2.0 * math.pi / 60.0, "rad/s": 1.0}
_TOP_LEVEL = {
    "schema",
    "schema_version",
    "case_id",
    "title",
    "model",
    "synthetic",
    "geometry",
    "operating_point",
    "sampling",
    "notes",
}


@dataclass(frozen=True)
class CaseLimits:
    """Software execution bounds, not a physical validity domain (see #4)."""

    max_document_bytes: int = 64 * 1024
    max_output_samples: int = 1_000_000
    max_revolutions: int = 1_000
    min_samples_per_revolution: int = 4
    max_samples_per_revolution: int = 7_200
    min_length_m: float = 1e-3
    max_length_m: float = 2.0
    min_speed_rad_s: float = 2.0 * math.pi / 60.0  # 1 rpm
    max_speed_rad_s: float = 20_000 * 2.0 * math.pi / 60.0  # 20 000 rpm


DEFAULT_LIMITS = CaseLimits()


def _reject_constant(value: str) -> float:
    raise ValueError(f"Non-finite JSON constant {value} is not allowed.")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key {key!r}.")
        result[key] = value
    return result


def decode_case(raw: bytes, limits: CaseLimits = DEFAULT_LIMITS) -> dict[str, Any]:
    """Decode strict UTF-8 JSON: no NaN/Infinity, duplicate keys or oversize payloads."""
    if len(raw) > limits.max_document_bytes:
        raise LimitExceeded(
            f"Case document exceeds {limits.max_document_bytes} bytes.",
            details=[FieldIssue("", f"{len(raw)} bytes received")],
        )
    try:
        document = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicates,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise InvalidInput(
            "Case document is not valid JSON.", details=[FieldIssue("", str(error))]
        ) from None
    if not isinstance(document, dict):
        raise InvalidInput("Case document must be a JSON object.")
    return document


def canonical_json(document: Mapping[str, Any]) -> bytes:
    """Stable bytes used for hashing and freezing the submitted case."""
    return (
        json.dumps(
            document, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


class _Collector:
    def __init__(self) -> None:
        self.issues: list[FieldIssue] = []
        self.provenance: dict[str, str] = {}

    def add(self, path: str, message: str) -> None:
        self.issues.append(FieldIssue(path, message))

    def obj(self, parent: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
        value = parent.get(key)
        if not isinstance(value, dict):
            self.add(path, "Required object is missing." if value is None else "Must be an object.")
            return {}
        return value

    def unknown(self, value: Mapping[str, Any], allowed: set[str], path: str) -> None:
        for key in sorted(set(value) - allowed):
            self.add(f"{path}.{key}" if path else key, "Unknown field.")

    def quantity(
        self,
        parent: Mapping[str, Any],
        key: str,
        path: str,
        units: Mapping[str, float],
        bounds: tuple[float, float],
        si_unit: str,
    ) -> float | None:
        value = self.obj(parent, key, path)
        if not value:
            return None
        self.unknown(value, {"value", "unit", "source"}, path)
        number = value.get("value")
        unit = value.get("unit")
        source = value.get("source")
        ok = True
        if isinstance(number, bool) or not isinstance(number, int | float):
            self.add(f"{path}.value", "Must be a number.")
            ok = False
        elif not math.isfinite(number):
            self.add(f"{path}.value", "Must be finite.")
            ok = False
        if unit not in units:
            self.add(f"{path}.unit", f"Must be one of: {', '.join(sorted(units))}.")
            ok = False
        if not isinstance(source, str) or not source.strip():
            self.add(f"{path}.source", "A source or 'hypothèse de démo' is required.")
        else:
            self.provenance[path] = source.strip()
        if not ok:
            return None
        assert isinstance(number, int | float) and isinstance(unit, str)
        si = float(number) * units[unit]
        low, high = bounds
        if not low <= si <= high:
            self.add(f"{path}.value", f"Must resolve to [{low:g}, {high:g}] {si_unit}.")
            return None
        return si

    def integer(self, parent: Mapping[str, Any], key: str, path: str, low: int, high: int) -> int:
        value = parent.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            self.add(path, "Must be an integer.")
            return 0
        if not low <= value <= high:
            self.add(path, f"Must be between {low} and {high}.")
            return 0
        return value


def parse_case(document: Mapping[str, Any], limits: CaseLimits = DEFAULT_LIMITS) -> KinematicCase:
    """Validate a decoded document and return its SI-resolved case."""
    check = _Collector()
    if document.get("schema") != CASE_SCHEMA:
        check.add("schema", f"Must be {CASE_SCHEMA!r}.")
    version = document.get("schema_version")
    if version != CASE_SCHEMA_VERSION:
        raise UnsupportedModel(
            f"Unsupported case schema_version {version!r}; supported: {CASE_SCHEMA_VERSION}.",
            details=[FieldIssue("schema_version", f"Expected {CASE_SCHEMA_VERSION}.")],
        )
    model = document.get("model")
    if model not in SUPPORTED_MODELS:
        raise UnsupportedModel(
            f"Unsupported model {model!r}; supported: {', '.join(sorted(SUPPORTED_MODELS))}.",
            details=[FieldIssue("model", "Unsupported model.")],
        )
    check.unknown(document, _TOP_LEVEL, "")
    case_id = document.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
        check.add("case_id", "Must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}.")
    title = document.get("title", "")
    if not isinstance(title, str) or len(title) > 200:
        check.add("title", "Must be a string of at most 200 characters.")
    notes = document.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        check.add("notes", "Must be a string of at most 2000 characters.")
    synthetic = document.get("synthetic")
    if not isinstance(synthetic, bool):
        check.add("synthetic", "Must be true or false: declare whether inputs are synthetic.")

    lengths = (limits.min_length_m, limits.max_length_m)
    geometry = check.obj(document, "geometry", "geometry")
    check.unknown(geometry, {"bore", "stroke", "connecting_rod_length"}, "geometry")

    def length(key: str) -> float | None:
        return check.quantity(geometry, key, f"geometry.{key}", _LENGTH_UNITS, lengths, "m")

    bore = length("bore")
    stroke = length("stroke")
    rod = length("connecting_rod_length")
    if stroke is not None and rod is not None and rod <= stroke / 2.0:
        check.add(
            "geometry.connecting_rod_length",
            "Must be longer than the crank radius (stroke / 2) for the slider-crank to close.",
        )

    operating = check.obj(document, "operating_point", "operating_point")
    check.unknown(operating, {"crank_speed"}, "operating_point")
    speed = check.quantity(
        operating,
        "crank_speed",
        "operating_point.crank_speed",
        _SPEED_UNITS,
        (limits.min_speed_rad_s, limits.max_speed_rad_s),
        "rad/s",
    )

    sampling = check.obj(document, "sampling", "sampling")
    check.unknown(sampling, {"revolutions", "samples_per_revolution"}, "sampling")
    revolutions = check.integer(
        sampling, "revolutions", "sampling.revolutions", 1, limits.max_revolutions
    )
    per_revolution = check.integer(
        sampling,
        "samples_per_revolution",
        "sampling.samples_per_revolution",
        limits.min_samples_per_revolution,
        limits.max_samples_per_revolution,
    )
    if check.issues:
        raise InvalidInput("Case document is invalid.", details=check.issues)
    samples = revolutions * per_revolution + 1
    if samples > limits.max_output_samples:
        raise LimitExceeded(
            f"Case requests {samples} output samples; the limit is {limits.max_output_samples}.",
            details=[FieldIssue("sampling", "Reduce revolutions or samples_per_revolution.")],
        )
    assert bore is not None and stroke is not None and rod is not None and speed is not None
    assert isinstance(case_id, str) and isinstance(title, str) and isinstance(synthetic, bool)
    return KinematicCase(
        case_id=case_id,
        title=title,
        bore_m=bore,
        stroke_m=stroke,
        connecting_rod_length_m=rod,
        crank_speed_rad_s=speed,
        revolutions=revolutions,
        samples_per_revolution=per_revolution,
        synthetic=synthetic,
        provenance=check.provenance,
    )
