#!/usr/bin/env python3
"""Gate D structural audit with exact OSM bus/psv access precedence.

OSM modal access is hierarchical: bus is more specific than psv, which is more
specific than generic vehicle/motor_vehicle/access restrictions. This wrapper keeps
all v3 candidate, provenance and structural-network behaviour while making that
precedence explicit and fail-closed for unparsed bus/psv access values.
"""
from __future__ import annotations

from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_structural_candidates_v3 as v3

base = v3.base
routing = v3.routing

CONDITIONAL_ACCESS = {"destination", "customers", "delivery"}
EXPLICIT_ALLOW = {"yes", "designated", "permissive"}


def _modal_access(tags: dict[str, str], key: str):
    raw = str(tags.get(key, "")).strip().lower()
    if not raw:
        return None, []
    if raw in routing.ACCESS_DENY:
        return False, []
    if raw in EXPLICIT_ALLOW:
        return True, []
    if raw in CONDITIONAL_ACCESS:
        return True, [f"conditional_{key}={raw}"]
    return False, [f"unparsed_{key}={raw}"]


def bus_eligibility(row) -> tuple[bool, list[str]]:
    highway = str(row.get("highway") or "")
    if highway not in routing.BUS_HIGHWAYS:
        return False, [f"highway={highway or 'missing'}"]

    tags = routing.row_tags(row)
    uncertainty: list[str] = []

    # Most-specific OSM mode wins. A bus=yes may override psv=no; conversely
    # bus=no must still deny even when psv=yes.
    bus_decision, bus_notes = _modal_access(tags, "bus")
    uncertainty.extend(bus_notes)
    if "bus" in tags and bus_decision is False:
        return False, bus_notes or ["explicit_bus_restriction"]
    if bus_decision is True:
        specific_allow = True
    else:
        psv_decision, psv_notes = _modal_access(tags, "psv")
        uncertainty.extend(psv_notes)
        if "psv" in tags and psv_decision is False:
            return False, psv_notes or ["explicit_psv_restriction"]
        specific_allow = psv_decision is True

    # Only when bus/psv has not explicitly authorised the mode do generic
    # restrictions control eligibility.
    if not specific_allow:
        for key in ("access", "vehicle", "motor_vehicle"):
            value = str(tags.get(key, "")).strip().lower()
            if value in routing.ACCESS_DENY:
                return False, [f"explicit_{key}_restriction"]
            if value in CONDITIONAL_ACCESS:
                uncertainty.append(f"conditional_{key}={value}")

    for key in ("maxheight", "maxweight", "maxwidth", "width", "lanes"):
        if key not in tags:
            uncertainty.append(f"missing_{key}")
    _, oneway_uncertainty = routing.oneway_direction(tags)
    if oneway_uncertainty:
        uncertainty.append(oneway_uncertainty)
    return True, sorted(set(uncertainty))


routing.bus_eligibility = bus_eligibility
base.routing.bus_eligibility = bus_eligibility


def main() -> int:
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
