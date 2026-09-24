"""Arithmetic-only south-spur resource sensitivity; never a composed route."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "profiles": "03105f27fa3b979fb02e84da9ccdaad42134b9b3c6d1123792ba190e93ffe72a",
    "road_probe": "e67b36b1f72e34e81cf027e5581fa295cd287cce8ff67318d95aea11c4ba8f99",
    "policy": "ec724d53b26fa5693be8ac98935bfc98087d380af7e557ed5b65ff8cede290be",
}
DAILY_CYCLES = 20
SERVICE_DAYS = 260


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def overlay_annual_km(base_distance_m, two_way_probe_distance_m):
    return ((Decimal(base_distance_m) + Decimal(two_way_probe_distance_m))
            * DAILY_CYCLES * SERVICE_DAYS / 1000)


def main(paths, output):
    for name, path in paths.items():
        if sha256(path) != EXPECTED[name]:
            raise ValueError(f"pinned source drift: {name}")
    frontier = json.loads(paths["profiles"].read_text(encoding="utf-8"))
    probe = json.loads(paths["road_probe"].read_text(encoding="utf-8"))
    policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
    profiles = frontier["profiles"]
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    if (len(profiles) != 736 or frontier["network_selected"] is not False
            or probe["status"] != "NON_DECISIONAL_CONDITIONAL_MODEL_PATHS_NOT_FIELD_CERTIFIED"
            or probe["route_insertion_into_one_line_certified"] is not False
            or policy["human_policy_decisions"]["budget_semantics"] != "HARD_CAP_NOT_TARGET; candidates may use materially less production."):
        raise ValueError("upstream semantic drift")
    two_way = sum((Decimal(str(trip["distance_m"]))
                   for trip in probe["trips"].values()), Decimal(0))
    if len(probe["trips"]) != 2 or two_way <= 0:
        raise ValueError("bidirectional model probe incomplete")
    under = []
    for profile in profiles:
        annual = overlay_annual_km(profile["total_distance_m"], two_way)
        if annual <= cap:
            under.append((profile, annual))
    high_retention = sorted(
        ((profile, annual) for profile, annual in under
         if profile["retained_current_exact_stop_count"] >= 7),
        key=lambda row: row[0]["profile_id"])
    payload = {
        "contract": "RT031_SOUTH_SPUR_ARITHMETIC_RESOURCE_OVERLAY_V3",
        "status": "NON_DECISIONAL_NOT_A_COMPOSED_ROUTE_OR_TIMETABLE",
        "input_sha256": EXPECTED,
        "annual_bus_km_human_approved_cap": str(cap),
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "scenario_daily_cycles": DAILY_CYCLES,
        "scenario_service_days": SERVICE_DAYS,
        "scenario_is_not_selected": True,
        "two_way_probe_distance_m_rounded_sum": str(two_way),
        "full_existing_carrier_retained_without_rerouting_assumption": True,
        "existing_profile_count": len(profiles),
        "profiles_under_cap_in_arithmetic_overlay": len(under),
        "profiles_under_cap_with_at_least_7_of_11_current_exact_stops":
            len(high_retention),
        "high_retention_arithmetic_witnesses": [
            {"profile_id": profile["profile_id"],
             "base_cycle_distance_m": profile["total_distance_m"],
             "overlay_annual_bus_km": str(annual),
             "retained_current_exact_stop_count": profile["retained_current_exact_stop_count"],
             "exact_total_10min_walk_access": profile["exact_total_coverage"]["10"],
             "exact_brivio_10min_walk_access":
                 profile["exact_municipality_coverage"]["97010"]["10"]}
            for profile, annual in high_retention],
        "overlay_proves_legal_seam_turns": False,
        "overlay_proves_stop_safety_or_passenger_service": False,
        "overlay_satisfies_headway_policy": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in EXPECTED:
        parser.add_argument(f"--{name.replace('_', '-')}", dest=name,
                            type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main({name: getattr(args, name) for name in EXPECTED}, args.output)
