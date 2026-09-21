"""Audit unfiltered Arlate-priority discovery, preserving truncation semantics."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


HUB = "FROZEN::L00407"
BRIVIO = "FROZEN::300063"
SANTA = "FROZEN::300805"
ARLATE = frozenset(("ASF::ARLATE_BIVIO_PER_IL_PAESE",
                   "ASF::ARLATE_CANTINA_PIROVANO"))
PREFERRED = ARLATE | {BRIVIO, SANTA}
REFERENCE_CAP_KM = Decimal("111419")


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def audit(source):
    if (source.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or source.get("status") not in (
                "RESOURCE_LIMIT_INCOMPLETE",
                "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN")
            or source.get("search_priority_mode") != "preferred_stop_count"
            or source.get("required_root_stop_id") != HUB
            or source.get("conditional_span_minutes") != 600
            or source.get("execution_expansion_limit") != 500000
            or set(source.get("preferred_stop_ids_present_in_domain", ()))
            != PREFERRED
            or source.get("candidate_generation_priority_is_normative_selection")
            is not False
            or source.get("final_recommendation") is not False):
        raise ValueError("Arlate priority discovery contract drift")
    if (Decimal(source["distance_budget_m"]) * 20 * 260 / 1000
            > REFERENCE_CAP_KM):
        raise ValueError("reference distance envelope exceeded")
    if ((source["status"] == "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN")
            != (source.get("exhaustive") is True)
            or (source.get("exhaustive") is True
                and source.get("pending_heap_entries") != 0)):
        raise ValueError("search completion state drift")
    joint = []
    brivio_santa = 0
    for row in source["candidates"]:
        stops = set(row["available_stop_ids"])
        if HUB not in stops:
            raise ValueError("Olgiate FS absent from rooted witness")
        if {BRIVIO, SANTA} <= stops:
            brivio_santa += 1
            if stops & ARLATE:
                joint.append(row)
    return {
        "contract": "RT031_ARLATE_PRIORITY_PHYSICAL_DISCOVERY_AUDIT_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_DIAGNOSTIC",
        "search_exhaustive": source["exhaustive"],
        "expanded_states": source["expanded_states"],
        "pending_heap_entries": source["pending_heap_entries"],
        "physical_stop_set_count": len(source["candidates"]),
        "brivio_santa_co_present_count": brivio_santa,
        "brivio_santa_inner_arlate_co_present_count": len(joint),
        "joint_stop_set_ids": [row["stop_set_id"] for row in joint],
        "joint_minimum_found_distance_m": min(
            (row["minimum_found_distance_m"] for row in joint),
            key=Decimal, default=None),
        "brivio_stop_id": BRIVIO,
        "santa_maria_stop_id": SANTA,
        "arlate_any_stop_ids": sorted(ARLATE),
        "named_stops_are_search_priority_not_admission_rule": True,
        "absence_is_impossibility_proof": False,
        "physical_availability_is_ordered_service_event_guarantee": False,
        "candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }


def main(args):
    raw = args.search.read_bytes()
    output = audit(json.loads(raw))
    output["input_sha256"] = {"physical_search": hashlib.sha256(raw).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
