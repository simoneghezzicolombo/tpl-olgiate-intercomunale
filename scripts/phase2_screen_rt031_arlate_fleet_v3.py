"""Deterministic mixed-frequency fleet sensitivity for Arlate/Rovagnate lines."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    build_realization_catalog, load_inputs)
from scripts.phase2_screen_rt031_joint_frontier_fleet_v3 import (
    exact_fleet, canonical)
from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity)
from src.phase2_rt031_mixed_frequency_surface_v4 import (
    mixed_service_templates, phased_departures)


TYPED_PROFILES = {
    "rovagnate": (
        "84aaca4d89dfd149c3589a05bc97e0bc034bb615c57ea5e4c267bc84759a5520",
        "RT031_ARLATE_RETAINED_ONE_LINE_ACCESS_FRONTIER_V3", 3),
    "second_santa": (
        "4c7b571383f8308ef6bac290ea7961e6e4c0f4208b944ee2359f925040f28762",
        "RT031_ARLATE_SECOND_SANTA_ONE_LINE_ACCESS_V3", 2),
}
HUB = "FROZEN::L00407"


def main(args):
    digest, contract, count = TYPED_PROFILES[args.profile]
    if hashlib.sha256(args.typed.read_bytes()).hexdigest() != digest:
        raise ValueError("Arlate typed-line lineage drift")
    typed = json.loads(args.typed.read_text(encoding="utf-8"))
    if (typed.get("contract") != contract
            or len(typed.get("candidates", ())) != count
            or (args.profile == "rovagnate"
                and (typed.get("retention_subset_size") != 3
                     or typed.get("distinct_typed_path_count") != 3
                     or typed.get("single_recognizable_line_count") != 3))
            or (args.profile == "second_santa"
                and typed.get("typed_one_line_count") != 2)
            or typed.get("network_selected") is not False):
        raise ValueError("Arlate line contract drift")
    tables, hashes = load_inputs(args.inputs)
    if any(typed["input_sha256"].get(key) != value
           for key, value in hashes.items()):
        raise ValueError("physical source lineage drift")
    catalog, _ = build_realization_catalog(
        tables["patterns"], tables["corridors"], tables["edges"])
    edges = {row["edge_id"]: row for row in tables["edges"]}
    templates = mixed_service_templates()
    rows = []
    for row in typed["candidates"]:
        running = sum((Decimal(edges[edge]["running_minutes_model"])
                       for rid in row["realization_ids"]
                       for edge in catalog[rid]["edge_ids"]), Decimal(0))
        nonhub = sum(stop != HUB for stop in row["ordered_service_stop_ids"])
        screen = {
            "component_id": row["public_route_id"],
            "running_minutes_source_model_excludes_dwell": str(running),
            "nonhub_public_stop_event_count": nonhub,
        }
        engineering = engineering_cycle_sensitivity(
            [screen], headway_min=30)
        if engineering["case_count"] != 27:
            raise ValueError("inherited engineering sensitivity grid drift")
        by_template = {}
        for template in templates:
            departures = tuple(Decimal(str(value)) for value in
                               phased_departures(template, 0))
            counts = [exact_fleet(
                departures, Decimal(case["components"][0]
                                    ["cycle_minutes_source_model_sensitivity"]))
                for case in engineering["cases"]]
            by_template[template["template_id"]] = {
                "span_minutes": template["span_minutes"],
                "h30_peak_hours": template["h30_peak_hours"],
                "h60_offpeak_hours": template["h60_offpeak_hours"],
                "daily_departure_count": len(departures),
                "minimum_exact_vehicle_count": min(counts),
                "maximum_exact_vehicle_count": max(counts),
                "engineering_case_count_by_exact_vehicle_count": {
                    str(count): n for count, n in sorted(Counter(counts).items())},
            }
        rows.append({
            "path_id": row["path_id"],
            "running_minutes_source_model_excludes_dwell": str(running),
            "nonhub_public_stop_event_count": nonhub,
            "retained_current_exact_stop_count":
                row["retained_current_exact_stop_count"],
            "conditional_annual_carrier_km_at_20_daily_cycles": str(
                Decimal(row["distance_m"]) * 20 * 260 / 1000),
            "fleet_by_template": by_template,
        })
    output = {
        "contract": "RT031_ARLATE_ROVAGNATE_FLEET_SCREEN_V3",
        "status": "PASS_PROBE_SCOPED_DETERMINISTIC_FLEET_NON_DECISIONAL",
        "input_sha256": {"typed_line": digest, **hashes},
        "profile_scope": args.profile,
        "screened_line_count": len(rows),
        "engineering_cases_per_line_template": 27,
        "templates": [{k: v for k, v in template.items()
                       if k != "nominal_departure_minutes"}
                      for template in templates],
        "profiles": rows,
        "fleet_cap_declared_by_caller": False,
        "dwell_observed": False,
        "engineering_case_frequency_is_probability": False,
        "phase_rotation_evaluated_for_transfer_quality": False,
        "transfer_quality_evaluated": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
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
    parser.add_argument("--typed", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(TYPED_PROFILES),
                        default="rovagnate")
    main(parser.parse_args())
