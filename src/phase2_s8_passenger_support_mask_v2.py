"""Passenger-service support mask derived from audited S8 Phasing V2.

This module does not allocate passengers to routes and does not calculate GJT.
It only turns certified route geometry into explicit passenger-direction support,
then propagates those route-level facts into scenario-level counts.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Sequence

from src.phase2_s8_work_transfer_utility_v2 import (
    PassengerConnectionSupport,
    validate_s8_phase_opportunity_support,
)

SUPPORT_CONTRACT = "PHASE2_S8_PASSENGER_SUPPORT_MASK_V2"
SUPPORT_STATUS = "PASS_S8_PASSENGER_SUPPORT_MASK_V2_BUILD"
SUPPORT_EVIDENCE = "DERIVED_FROM_S8_PHASE_OPPORTUNITY_V2_PUBLIC_SERVICE_GEOMETRY"


@dataclass(frozen=True)
class PassengerSupportBuild:
    route_rows: tuple[dict[str, object], ...]
    scenario_rows: tuple[dict[str, object], ...]
    summary: dict[str, int]


def _route_class(support: PassengerConnectionSupport) -> str:
    if support.rail_to_bus_supported and support.bus_to_rail_supported:
        return "ROUNDTRIP_HUB_PASSENGER_SUPPORTED"
    if support.rail_to_bus_supported and not support.bus_to_rail_supported:
        return "RAIL_TO_BUS_ONLY_PUBLIC_ROUTE_OPEN_AWAY_FROM_HUB"
    raise ValueError("Unsupported passenger support state")


def build_route_support_rows(
    validation: Mapping[str, object],
    route_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, PassengerConnectionSupport]]:
    """Validate S8 geometry and emit one explicit support row per unique route."""
    supports = validate_s8_phase_opportunity_support(validation, route_rows)
    by_id = {str(row["route_id"]): row for row in route_rows}
    output: list[dict[str, object]] = []
    for route_id in sorted(supports):
        support = supports[route_id]
        row = by_id[route_id]
        output.append(
            {
                "route_id": route_id,
                "runtime_archetype_id": str(row.get("runtime_archetype_id", "")),
                "roles": str(row.get("roles", "")),
                "public_runtime_min": str(row.get("public_runtime_min", "")),
                "cycle_runtime_min": str(row.get("cycle_runtime_min", "")),
                "rail_to_bus_passenger_supported": support.rail_to_bus_supported,
                "bus_to_rail_passenger_supported": support.bus_to_rail_supported,
                "roundtrip_passenger_supported": (
                    support.rail_to_bus_supported and support.bus_to_rail_supported
                ),
                "passenger_support_class": _route_class(support),
                "support_evidence_status": support.evidence_status,
                "passenger_demand_assigned_to_route": False,
                "passenger_utility_calculated": False,
            }
        )
    return output, supports


def _parse_route_ids(raw: object, *, field: str, scenario_id: str) -> list[str]:
    try:
        values = json.loads(str(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{scenario_id}: invalid {field}") from exc
    if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
        raise ValueError(f"{scenario_id}: {field} must be a JSON list of route IDs")
    if len(values) != len(set(values)):
        raise ValueError(f"{scenario_id}: duplicate route ID inside {field}")
    return values


def build_scenario_support_rows(
    mapping_rows: Sequence[Mapping[str, object]],
    supports: Mapping[str, PassengerConnectionSupport],
) -> list[dict[str, object]]:
    """Propagate route support into counts only, never into passenger demand."""
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    known_routes = set(supports)
    for row in mapping_rows:
        scenario_id = str(row.get("scenario_id", "")).strip()
        if not scenario_id or scenario_id in seen:
            raise ValueError("Scenario mapping has missing or duplicate scenario_id")
        seen.add(scenario_id)
        public_ids = _parse_route_ids(
            row.get("public_route_ids_json", "[]"),
            field="public_route_ids_json",
            scenario_id=scenario_id,
        )
        extension_ids = _parse_route_ids(
            row.get("extension_route_ids_json", "[]"),
            field="extension_route_ids_json",
            scenario_id=scenario_id,
        )
        unknown = sorted((set(public_ids) | set(extension_ids)) - known_routes)
        if unknown:
            raise ValueError(f"{scenario_id}: scenario references unknown route IDs: {unknown[:3]}")

        def counts(route_ids: list[str]) -> tuple[int, int]:
            roundtrip = sum(
                supports[r].rail_to_bus_supported and supports[r].bus_to_rail_supported
                for r in route_ids
            )
            r2b_only = sum(
                supports[r].rail_to_bus_supported and not supports[r].bus_to_rail_supported
                for r in route_ids
            )
            if roundtrip + r2b_only != len(route_ids):
                raise ValueError(f"{scenario_id}: route support accounting is incomplete")
            return int(roundtrip), int(r2b_only)

        public_roundtrip, public_r2b_only = counts(public_ids)
        extension_roundtrip, extension_r2b_only = counts(extension_ids)
        output.append(
            {
                "scenario_id": scenario_id,
                "topology_family": str(row.get("topology_family", "")),
                "public_route_count": len(public_ids),
                "public_roundtrip_supported_route_count": public_roundtrip,
                "public_rail_to_bus_only_route_count": public_r2b_only,
                "extension_route_count": len(extension_ids),
                "extension_roundtrip_supported_route_count": extension_roundtrip,
                "extension_rail_to_bus_only_route_count": extension_r2b_only,
                "passenger_demand_assigned_to_routes": False,
                "scenario_passenger_utility_calculated": False,
                "topology_ranked": False,
            }
        )
    if not output:
        raise ValueError("Scenario support universe is empty")
    return output


def summarise_support(
    route_rows: Sequence[Mapping[str, object]],
    scenario_rows: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    roundtrip = sum(bool(r["roundtrip_passenger_supported"]) for r in route_rows)
    r2b_only = len(route_rows) - roundtrip
    return {
        "route_count": len(route_rows),
        "roundtrip_passenger_supported_route_count": int(roundtrip),
        "rail_to_bus_only_route_count": int(r2b_only),
        "scenario_count": len(scenario_rows),
        "scenario_public_route_occurrence_count": sum(int(r["public_route_count"]) for r in scenario_rows),
        "scenario_public_roundtrip_route_occurrence_count": sum(
            int(r["public_roundtrip_supported_route_count"]) for r in scenario_rows
        ),
        "scenario_public_rail_to_bus_only_route_occurrence_count": sum(
            int(r["public_rail_to_bus_only_route_count"]) for r in scenario_rows
        ),
        "scenario_extension_route_occurrence_count": sum(int(r["extension_route_count"]) for r in scenario_rows),
        "scenario_extension_roundtrip_route_occurrence_count": sum(
            int(r["extension_roundtrip_supported_route_count"]) for r in scenario_rows
        ),
        "scenario_extension_rail_to_bus_only_route_occurrence_count": sum(
            int(r["extension_rail_to_bus_only_route_count"]) for r in scenario_rows
        ),
    }
