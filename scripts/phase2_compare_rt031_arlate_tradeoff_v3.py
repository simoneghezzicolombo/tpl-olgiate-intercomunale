"""No-weight comparison of five Arlate/Rovagnate lines and two earlier lines."""
import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_municipal_access_frontier_v4 import exact_pareto_indices


ARLATE_SHA256 = "84aaca4d89dfd149c3589a05bc97e0bc034bb615c57ea5e4c267bc84759a5520"
SECOND_SANTA_SHA256 = "4c7b571383f8308ef6bac290ea7961e6e4c0f4208b944ee2359f925040f28762"
JOINT_SHA256 = "f98ff97d4ef22a44b03474ef986c76a253be2cb8016f3aca38b044526d5c98a8"
JOINT_IDS = ("WALK_8586d7e865308d0510c6",
             "WALK_e5d89184ad2835c735e1")
THRESHOLDS = ("5", "8", "10")


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(row, codes):
    return (tuple(Fraction(row["exact_total_coverage"][t])
                  for t in THRESHOLDS)
            + tuple(Fraction(row["exact_municipality_coverage"][code][t])
                    for code in codes for t in THRESHOLDS)
            + (Fraction(row["retained_current_exact_stop_count"], 11),))


def main(args):
    if (sha256(args.arlate) != ARLATE_SHA256
            or sha256(args.second_santa) != SECOND_SANTA_SHA256
            or sha256(args.joint) != JOINT_SHA256):
        raise ValueError("typed comparison lineage drift")
    arlate = json.loads(args.arlate.read_text(encoding="utf-8"))
    second = json.loads(args.second_santa.read_text(encoding="utf-8"))
    joint = json.loads(args.joint.read_text(encoding="utf-8"))
    if (arlate.get("contract") != "RT031_ARLATE_RETAINED_ONE_LINE_ACCESS_FRONTIER_V3"
            or arlate.get("retention_subset_size") != 3
            or arlate.get("required_additional_current_stop_id") != "FROZEN::300879"
            or arlate.get("distinct_typed_path_count") != 3
            or arlate.get("single_recognizable_line_count") != 3
            or second.get("contract") != "RT031_ARLATE_SECOND_SANTA_ONE_LINE_ACCESS_V3"
            or second.get("typed_one_line_count") != 2
            or joint.get("contract") != "RT031_JOINT_DISCOVERY_TYPED_FRONTIER_V3"
            or joint.get("candidate_count") != 99
            or arlate.get("current_exact_id_structural_subset")
            != joint.get("current_exact_id_structural_subset")
            or second.get("current_exact_id_structural_subset")
            != joint.get("current_exact_id_structural_subset")
            or any(source.get("network_selected") is not False
                   or source.get("primary_selection_authorised") is not False
                   or source.get("runner_up_selection_authorised") is not False
                   for source in (arlate, second, joint))):
        raise ValueError("typed comparison contract drift")
    prior = {row["stop_set_id"]: row for row in joint["candidates"]
             if row["stop_set_id"] in JOINT_IDS}
    if set(prior) != set(JOINT_IDS):
        raise ValueError("earlier comparator identity drift")
    candidates = [(row["path_id"], "ARLATE_ROVAGNATE_PROBE", row)
                  for row in arlate["candidates"]]
    candidates += [(row["path_id"], "ARLATE_ROVAGNATE_SECOND_SANTA_PROBE", row)
                   for row in second["candidates"]]
    candidates += [(identity, "EARLIER_BRIVIO_SANTA_PROBE", prior[identity])
                   for identity in JOINT_IDS]
    if len({identity for identity, _, _ in candidates}) != 7:
        raise ValueError("seven distinct comparison identities required")
    codes = sorted(arlate["current_exact_id_structural_subset"]["municipal"])
    benefits = [vector(row, codes) for _, _, row in candidates]
    costs = [Decimal(row["distance_m"]) for _, _, row in candidates]
    frontier = exact_pareto_indices(benefits, costs)
    rows = []
    for identity, lane, row in candidates:
        rows.append({
            "identity": identity,
            "lane": lane,
            "distance_m": row["distance_m"],
            "available_stop_count": len(row["available_stop_ids"]),
            "retained_current_exact_stop_count":
                row["retained_current_exact_stop_count"],
            "total_potential_walking_share": row["exact_total_coverage"],
            "municipality_potential_walking_share":
                row["exact_municipality_coverage"],
            "single_recognizable_line_structure_certified":
                row["single_recognizable_line_structure_certified"],
        })
    output = {
        "contract": "RT031_ARLATE_ROVAGNATE_COMBINED_TRADEOFF_V3",
        "status": "PASS_SEVEN_LINE_PROBE_SCOPED_NON_DECISIONAL_PARETO",
        "input_sha256": {"arlate_rovagnate_typed": ARLATE_SHA256,
                         "second_santa_typed": SECOND_SANTA_SHA256,
                         "earlier_joint_typed": JOINT_SHA256},
        "comparison_line_count": len(rows),
        "combined_probe_pareto_count": len(frontier),
        "combined_probe_pareto_ids": [rows[index]["identity"]
                                      for index in frontier],
        "pareto_axes": ["total_potential_walk_5_8_10",
                        "each_municipality_potential_walk_5_8_10",
                        "current_exact_stop_retention_preference",
                        "physical_distance_cost"],
        "municipality_codes": codes,
        "rows": rows,
        "coverage_is_potential_walking_not_observed_passenger_demand": True,
        "line_set_is_exhaustive_candidate_domain": False,
        "stop_retention_is_preference_not_filter": True,
        "fleet_screen_completed_for_new_lines": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arlate", type=Path, required=True)
    parser.add_argument("--second-santa", type=Path, required=True)
    parser.add_argument("--joint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
