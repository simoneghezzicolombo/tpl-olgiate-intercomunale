"""Exact deterministic vehicle screen for found joint one-line Pareto points."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import heapq
import json
from pathlib import Path

from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity)
from src.phase2_rt031_mixed_frequency_surface_v4 import (
    mixed_service_templates, phased_departures)


TYPED_SHA256 = "f98ff97d4ef22a44b03474ef986c76a253be2cb8016f3aca38b044526d5c98a8"
SEARCH_SHA256 = "11353efb3609cdd9d5c464a685697e34838a30f32d0f70e6a1fe71cbabe31c89"
HUB = "FROZEN::L00407"


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def exact_fleet(departures, cycle_minutes):
    if cycle_minutes <= 0:
        raise ValueError("positive cycle minutes required")
    ready = []
    count = 0
    for departure in departures:
        if ready and ready[0] <= departure:
            heapq.heapreplace(ready, departure + cycle_minutes)
        else:
            heapq.heappush(ready, departure + cycle_minutes)
            count += 1
    return count


def main(args):
    if (hashlib.sha256(args.typed.read_bytes()).hexdigest() != TYPED_SHA256
            or hashlib.sha256(args.search.read_bytes()).hexdigest()
            != SEARCH_SHA256):
        raise ValueError("typed or physical source lineage drift")
    typed = json.loads(args.typed.read_text(encoding="utf-8"))
    physical = json.loads(args.search.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_JOINT_DISCOVERY_TYPED_FRONTIER_V3"
            or typed.get("candidate_count") != 99
            or typed.get("source_search_exhaustive") is not False
            or typed.get("network_selected") is not False):
        raise ValueError("typed joint candidate contract drift")
    found = {row["stop_set_id"]: row for row in physical["candidates"]}
    frontier_ids = typed["exact_within_found_set_pareto_stop_set_ids"]
    if len(frontier_ids) != 10 or len(set(frontier_ids)) != 10:
        raise ValueError("ten distinct found-set Pareto points required")
    selected = {row["stop_set_id"]: row for row in typed["candidates"]
                if row["stop_set_id"] in frontier_ids}
    if set(selected) != set(frontier_ids):
        raise ValueError("typed Pareto identity drift")
    templates = mixed_service_templates()
    rows = []
    for identity in frontier_ids:
        row = selected[identity]
        source = found[identity]
        if row["realization_ids"] != source["realization_ids"]:
            raise ValueError("ordered physical witness drift")
        nonhub = sum(stop != HUB for stop in row["ordered_service_stop_ids"])
        screen = {
            "component_id": row["public_route_id"],
            "running_minutes_source_model_excludes_dwell":
                source["running_minutes_source_model"],
            "nonhub_public_stop_event_count": nonhub,
        }
        engineering = engineering_cycle_sensitivity(
            [screen], headway_min=30)
        if engineering["case_count"] != 27:
            raise ValueError("inherited deterministic grid drift")
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
            "stop_set_id": identity,
            "running_minutes_source_model_excludes_dwell":
                source["running_minutes_source_model"],
            "nonhub_public_stop_event_count": nonhub,
            "retained_current_exact_stop_count":
                row["retained_current_exact_stop_count"],
            "conditional_annual_carrier_km_at_20_daily_cycles":
                source["conditional_annual_carrier_km_h30_260days"],
            "fleet_by_template": by_template,
        })
    output = {
        "contract": "RT031_JOINT_DISCOVERY_FLEET_SCREEN_V3",
        "status": "PASS_FOUND_SET_PARETO_FLEET_SCREEN_NON_DECISIONAL",
        "input_sha256": {"typed_joint_frontier": TYPED_SHA256,
                         "physical_search": SEARCH_SHA256},
        "found_set_pareto_line_count": len(rows),
        "engineering_cases_per_line_template": 27,
        "templates": [
            {k: v for k, v in template.items()
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
    print(json.dumps(output, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed", type=Path, required=True)
    parser.add_argument("--search", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
