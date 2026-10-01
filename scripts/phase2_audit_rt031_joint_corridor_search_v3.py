#!/usr/bin/env python3
"""Audit a bounded Brivio/Santa Maria priority search without selecting a line."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


BRIVIO = "FROZEN::300063"
SANTA_MARIA = frozenset(("FROZEN::300782", "FROZEN::300805",
                         "FROZEN::300873"))
PREFERRED = SANTA_MARIA | {BRIVIO}
HUB = "FROZEN::L00407"
REFERENCE_CAP_KM = Decimal("111419")
DAILY_CYCLES = 20
DESIGN_DAYS = 260


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def audit_search(source):
    if (source.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or source.get("status") not in (
                "RESOURCE_LIMIT_INCOMPLETE",
                "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN")
            or source.get("search_priority_mode") != "preferred_stop_count"
            or source.get("required_root_stop_id") != HUB
            or source.get("conditional_span_minutes") != 600
            or source.get("execution_expansion_limit") != 500000
            or set(source.get("preferred_stop_ids_present_in_domain", ())) != PREFERRED
            or source.get("candidate_generation_priority_is_normative_selection") is not False
            or source.get("final_recommendation") is not False):
        raise ValueError("bounded joint-corridor search contract drift")
    if (Decimal(source["distance_budget_m"]) * DAILY_CYCLES
            * DESIGN_DAYS / 1000 > REFERENCE_CAP_KM):
        raise ValueError("physical distance envelope exceeds reference cap")
    if ((source["status"] == "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN")
            != (source.get("exhaustive") is True)
            or (source.get("exhaustive") is True
                and source.get("pending_heap_entries") != 0)):
        raise ValueError("physical search completion state drift")
    candidates = source["candidates"]
    joint = []
    for row in candidates:
        stops = set(row["available_stop_ids"])
        if HUB not in stops:
            raise ValueError("hub-rooted witness lacks Olgiate FS")
        if BRIVIO in stops and stops & SANTA_MARIA:
            joint.append(row)
    return {
        "contract": "RT031_BRIVIO_SANTA_MARIA_JOINT_CORRIDOR_AUDIT_V3",
        "status": "PASS_BOUNDED_SEARCH_DIAGNOSTIC_NO_SELECTION",
        "search_exhaustive": source["exhaustive"],
        "search_expanded_states": source["expanded_states"],
        "search_pending_heap_entries": source["pending_heap_entries"],
        "physical_candidate_count": len(candidates),
        "joint_brivio_at_least_one_santa_maria_candidate_count": len(joint),
        "joint_candidate_stop_set_ids": [row["stop_set_id"] for row in joint],
        "joint_minimum_found_distance_m": min((row[
            "minimum_found_distance_m"] for row in joint),
            key=Decimal, default=None),
        "brivio_stop_id": BRIVIO,
        "santa_maria_stop_ids": sorted(SANTA_MARIA),
        "preferred_stops_are_search_priority_not_admission_rule": True,
        "physical_availability_is_ordered_service_event_guarantee": False,
        "absence_is_impossibility_proof": False,
        "distance_budget_m": source["distance_budget_m"],
        "reference_cap_km": str(REFERENCE_CAP_KM),
        "daily_cycles": DAILY_CYCLES,
        "annual_design_days": DESIGN_DAYS,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }


def main(args):
    raw = args.search.read_bytes()
    output = audit_search(json.loads(raw))
    output["input_sha256"] = {"physical_search": hashlib.sha256(raw).hexdigest()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "joint_corridor_search_audit_v3.json").write_bytes(
        canonical(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
