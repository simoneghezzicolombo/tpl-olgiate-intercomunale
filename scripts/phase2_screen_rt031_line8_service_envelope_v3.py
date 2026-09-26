"""Conditional kilometre envelope for the two Linea 8 stop-retention variants.

This is arithmetic on modeled full traversals, not a timetable or finalizer.
"""

import argparse
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
from pathlib import Path


OPTIONS = (
    "FOUR_QUATTRO_STRADE_THEN_CARIPLO",
    "FIVE_QUATTRO_STRADE_THEN_CARIPLO",
)
SCENARIOS = (
    ("H60_8H", 8),
    ("H60_10H", 10),
    ("H60_16H", 16),
    ("H30_4H_PLUS_H60_12H", 20),
)
DAYS = 260


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def main(policy_path, repair_path, output_path):
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    if policy["contract"] != "PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3":
        raise ValueError("policy contract mismatch")
    if repair["contract"] != "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3":
        raise ValueError("repair contract mismatch")
    if repair["network_selected"] or repair["primary_selection_authorised"]:
        raise ValueError("repair evidence is unexpectedly decisional")
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    if cap <= 0:
        raise ValueError("invalid policy cap")
    variants = []
    for name in OPTIONS:
        row = repair["combined_repair_order_options"][name]
        if not row["reachable_both_directions"]:
            raise ValueError(f"unreachable variant: {name}")
        forward = Decimal(str(row["forward_complete_cycle_distance_m"])) / 1000
        reverse = Decimal(str(row["reverse_complete_cycle_distance_m"])) / 1000
        pair = forward + reverse
        west_pair = (Decimal(str(row["west_forward_lobe_distance_m"]))
                     + Decimal(str(row["west_reverse_lobe_distance_m"]))) / 1000
        east_pair = (Decimal(str(row["east_forward_lobe_distance_m"]))
                     + Decimal(str(row["east_reverse_lobe_distance_m"]))) / 1000
        if west_pair + east_pair != pair:
            raise ValueError(f"lobe/full distance mismatch: {name}")
        annual_per_pair = pair * DAYS
        maximum = int((cap / annual_per_pair).to_integral_value(rounding=ROUND_FLOOR))
        frontier = []
        max_west = int((cap / (west_pair * DAYS)).to_integral_value(rounding=ROUND_FLOOR))
        for west_daily_pairs in range(max_west + 1):
            remainder = cap - west_pair * DAYS * west_daily_pairs
            east_daily_pairs = int((remainder / (east_pair * DAYS)).to_integral_value(
                rounding=ROUND_FLOOR))
            frontier.append({
                "west_daily_bidirectional_lobe_pairs": west_daily_pairs,
                "east_daily_bidirectional_lobe_pairs": east_daily_pairs,
                "both_wings_served": west_daily_pairs > 0 and east_daily_pairs > 0,
                "annual_lobe_km_before_extras": float(DAYS * (
                    west_pair * west_daily_pairs + east_pair * east_daily_pairs)),
            })
        scenarios = []
        for scenario_id, daily_pairs in SCENARIOS:
            annual = annual_per_pair * daily_pairs
            scenarios.append({
                "scenario_id": scenario_id,
                "full_traversals_per_direction_per_day": daily_pairs,
                "assumed_annual_full_traversal_km": float(annual),
                "within_cap_before_any_extra_km": annual <= cap,
                "excess_over_cap_km_if_any": float(max(Decimal(0), annual - cap)),
            })
        variants.append({
            "variant_id": name,
            "current_exact_stop_ids_encountered_both_directions": row[
                "current_exact_stop_ids_encountered_count"],
            "forward_full_traversal_km": float(forward),
            "reverse_full_traversal_km": float(reverse),
            "daily_bidirectional_pair_km": float(pair),
            "west_daily_bidirectional_lobe_pair_km": float(west_pair),
            "east_daily_bidirectional_lobe_pair_km": float(east_pair),
            "maximum_east_pairs_for_each_west_count_before_extras": frontier,
            "maximum_integer_daily_bidirectional_pairs_within_cap_before_extras": maximum,
            "annual_km_at_that_maximum_before_extras": float(annual_per_pair * maximum),
            "unused_cap_km_at_that_maximum_before_extras": float(cap - annual_per_pair * maximum),
            "scenarios": scenarios,
        })
    payload = {
        "contract": "RT031_LINE8_CONDITIONAL_COMPLETE_TRAVERSAL_RESOURCE_ENVELOPE_V3",
        "status": "NON_DECISIONAL_MODEL_ARITHMETIC_ONLY",
        "source_canonical_sha256": {"policy": canonical_sha256(policy),
                                    "repair_screen": canonical_sha256(repair)},
        "approved_annual_bus_km_cap": float(cap),
        "assumed_annual_service_days": DAYS,
        "assumption": "Each departure counted here operates one entire west-plus-east full traversal in its declared direction; one daily pair is one forward and one reverse full traversal. Half-open integer-hour windows are assumed for scenario counts.",
        "not_certified": ["full-history route legality", "safe boarding events",
                          "dwell-inclusive runtime", "timetable phases", "fleet",
                          "rail connections", "depot/repositioning km", "Saturday service",
                          "short-turn or interlined service alternative"],
        "variants": variants,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--repair", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.policy, args.repair, args.output)
