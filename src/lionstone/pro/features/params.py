"""Parameter schemas: bounded, typed, validated. Invalid values are rejected, never guessed."""

from __future__ import annotations

import math
import re
from typing import Any

_HEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


class ParamError(ValueError):
    pass


def validate_value(name: str, spec: dict, value: Any) -> Any:
    t = spec.get("type", "number")
    if t in ("number", "int"):
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError as e:
                raise ParamError(f"{name}: expected a number, got {value!r}") from e
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParamError(f"{name}: expected a number, got {value!r}")
        if math.isnan(value) or math.isinf(value):
            raise ParamError(f"{name}: NaN / infinite values are not allowed")
        lo, hi = spec.get("min", -math.inf), spec.get("max", math.inf)
        if not lo <= value <= hi:
            raise ParamError(f"{name}={value} outside [{lo}, {hi}]")
        return int(round(value)) if t == "int" else float(value)
    if t == "enum":
        if value not in spec["values"]:
            raise ParamError(f"{name}: {value!r} not in {spec['values']}")
        return value
    if t == "bool":
        if isinstance(value, str):
            if value.lower() in ("1", "true", "yes", "on"):
                return True
            if value.lower() in ("0", "false", "no", "off"):
                return False
        if not isinstance(value, bool):
            raise ParamError(f"{name}: expected true/false")
        return value
    if t == "color":
        if not isinstance(value, str) or not _HEX.match(value):
            raise ParamError(f"{name}: expected a #RRGGBB color, got {value!r}")
        return "#" + value.lstrip("#").upper()
    if t == "string":
        if not isinstance(value, str) or len(value) > spec.get("maxLength", 500):
            raise ParamError(f"{name}: expected text (max {spec.get('maxLength', 500)} chars)")
        return value
    if t == "list":
        if not isinstance(value, list):
            raise ParamError(f"{name}: expected a list")
        item = spec.get("items", {"type": "number"})
        return [validate_value(f"{name}[{i}]", item, v) for i, v in enumerate(value)]
    if t == "keyframes":
        from .keyframes import validate_track
        return validate_track(name, value)
    raise ParamError(f"{name}: unknown parameter type {t!r}")


def resolve(schema: dict[str, dict], overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Defaults + validated overrides. Unknown parameter names are an error."""
    out = {k: spec.get("default") for k, spec in schema.items()}
    for k, v in (overrides or {}).items():
        if k not in schema:
            raise ParamError(f"unknown parameter {k!r}; known: {', '.join(schema) or '—'}")
        out[k] = validate_value(k, schema[k], v)
    return out


def parse_cli(pairs: list[str]) -> dict[str, Any]:
    """`k=v` pairs from the CLI; JSON-ish lists via comma (`times=1.2,3.4`)."""
    out: dict[str, Any] = {}
    for p in pairs:
        if "=" not in p:
            raise ParamError(f"expected key=value, got {p!r}")
        k, v = p.split("=", 1)
        if "," in v and not v.startswith("#"):
            out[k] = [float(x) for x in v.split(",") if x.strip()]
        else:
            out[k] = v
    return out
