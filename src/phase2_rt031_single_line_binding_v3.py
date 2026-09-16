"""Fail-closed binding for one recognizable public line candidate.

This contract certifies candidate design structure only.  It does not certify a
timetable, observed running time, vehicle block, or a selected network.
"""
from __future__ import annotations

from fractions import Fraction
from decimal import Decimal


def eligible_h30_10h_candidates(frontier, *, current_exact_ratios):
    """Return exact-access improvements inside the H30/10h reference context.

    Retention is deliberately not a filter: it remains a Pareto preference.
    """
    current = tuple(Fraction(value) for value in current_exact_ratios)
    if len(current) != 6:
        raise ValueError("six exact current-access ratios required")
    eligible = []
    identities = set()
    for row in frontier:
        identity = row.get("candidate_line_id")
        ratios = tuple(Fraction(value) for value in row.get("exact_access_ratios", ()))
        if (not identity or identity in identities or len(ratios) != 6
                or row.get("physical_closed_walk_count") != 1
                or row.get("intended_public_route_identity_count") != 1):
            raise ValueError("single-line frontier identity/semantics drift")
        identities.add(identity)
        contexts = [item for item in row.get("service_surface", ())
                    if item.get("uniform_headway_min_per_movement") == 30
                    and item.get("span_minutes") == 600]
        if len(contexts) != 1:
            raise ValueError("unique H30/10h service context required")
        if (all(value >= benchmark for value, benchmark in zip(ratios, current))
                and any(value > benchmark for value, benchmark in zip(ratios, current))
                and contexts[0].get("within_approved_reference_cap") is True):
            eligible.append(row)
    return sorted(eligible, key=lambda row: row["candidate_line_id"])


def municipal_frontier_within_cap(frontier, *, annual_bus_km_cap):
    """Validate and return the municipal-axis frontier inside a declared cap.

    Municipal non-regression and current-stop retention deliberately remain
    Pareto dimensions rather than admission filters.
    """
    cap = Decimal(str(annual_bus_km_cap))
    if not cap.is_finite() or cap <= 0:
        raise ValueError("positive finite annual bus-km cap required")
    selected = []
    identities = set()
    for row in frontier:
        identity = row.get("candidate_line_id")
        if not identity or identity in identities:
            raise ValueError("unique municipal-frontier candidate identity required")
        identities.add(identity)
        distance = Decimal(str(row.get("total_distance_m")))
        annual = Decimal(str(
            row.get("conditional_annual_bus_km_at_20_daily_cycles")))
        if (not distance.is_finite() or distance <= 0
                or not annual.is_finite() or annual <= 0):
            raise ValueError("positive finite candidate distance required")
        expected = distance * Decimal(20) * Decimal(260) / Decimal(1000)
        if annual != expected:
            raise ValueError("municipal-frontier resource identity drift")
        realization_ids = row.get("realization_ids", ())
        stops = row.get("available_stop_ids", ())
        municipal = row.get("exact_municipality_coverage", {})
        if (not realization_ids or not stops or "FROZEN::L00407" not in stops
                or len(municipal) != 5
                or any(set(values) != {"5", "8", "10"}
                       for values in municipal.values())):
            raise ValueError("municipal-frontier candidate semantics drift")
        if annual <= cap:
            selected.append(row)
    return sorted(selected, key=lambda row: row["candidate_line_id"])


def certify_single_public_line(network, *, public_route_id):
    """Certify the minimum route/event distinctions for one candidate line."""
    if not isinstance(public_route_id, str) or not public_route_id.strip():
        raise ValueError("one nonempty public route identity required")
    if (network.get("service_relations_complete") is not True
            or network.get("movement_assignment_complete") is not True):
        raise ValueError("typed service and movement assignment must be complete")
    payload = network.get("payload", {})
    components = payload.get("components", {})
    patterns = payload.get("patterns", ())
    movements = payload.get("movements", ())
    macros = payload.get("macro_incidence", ())
    if (len(components) != 1 or len(patterns) != 1 or len(movements) != 1
            or len(macros) != 1):
        raise ValueError("one line cannot relabel multiple independent service structures")
    if macros[0].get("source_stop") != macros[0].get("target_stop"):
        raise ValueError("single-line candidate must retain its closed-walk incidence")
    component_id, component = next(iter(components.items()))
    pattern, movement = patterns[0], movements[0]
    if (pattern.get("component_id") != component_id
            or movement.get("component_id") != component_id
            or movement.get("multiplicity") != 1
            or list(component.get("component", {}).get("macro_edge_ids", ()))
            != [macros[0].get("edge_id")]):
        raise ValueError("pattern/movement incidence differs from the sole component")
    events = component.get("events", ())
    event_ids = [row.get("event", {}).get("event_id") for row in events]
    if (not event_ids or any(not value for value in event_ids)
            or list(pattern.get("event_ids", ())) != event_ids):
        raise ValueError("public pattern must equal the full ordered event sequence")
    semantics = [row.get("event", {}) for row in events]
    required = ("pickup", "dropoff", "passenger_through", "vehicle_through")
    if any(event.get(field) is None for event in semantics for field in required):
        raise ValueError("every ordered occurrence needs explicit service semantics")
    if len(events) < 2 or semantics[-1].get("passenger_through") is not False:
        raise ValueError("passenger continuation across the cycle seam must fail closed")
    if any(event.get("passenger_through") is not True for event in semantics[1:-1]):
        raise ValueError("within-pattern passenger continuity must be explicit")
    if not (semantics[0].get("pickup") is True
            and semantics[0].get("dropoff") is False
            and semantics[0].get("passenger_through") is False
            and semantics[0].get("vehicle_through") is False
            and semantics[-1].get("pickup") is False
            and semantics[-1].get("dropoff") is True
            and semantics[-1].get("vehicle_through") is False):
        raise ValueError("cycle seam needs distinct departure and arrival semantics")
    return {
        "public_route_id": public_route_id,
        "public_route_identity_count": 1,
        "service_component_id": component_id,
        "public_pattern_id": pattern["pattern_id"],
        "movement_id": movement["movement_id"],
        "declared_movement_multiplicity": movement["multiplicity"],
        "ordered_service_event_ids": event_ids,
        "passenger_service_continuity_scope": "WITHIN_ORDERED_PATTERN_ONLY",
        "cycle_seam_passenger_through": False,
        "vehicle_continuity_used_as_passenger_continuity": False,
        "single_recognizable_line_structure_certified": True,
        "certificate_semantics": "EXPLICIT_CANDIDATE_DESIGN_NOT_OBSERVED_SERVICE",
    }
