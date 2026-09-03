#!/usr/bin/env python3
"""Materialise the Phase 2 V2 family-balanced structural catalog.

This is a thin V2 contract around the already-audited topology-neutral balanced
search engine. It changes no structural-search algorithm. It exists to preserve
and validate the more specific epistemic states carried by Stop Universe V2 and
Reduced Path Matrix V2 rather than flattening them to generic FACT/DERIVED labels.

The output is a structural search catalog, not a network recommendation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_balanced_structural_search import hub_bidirectional_anchor_filter
from scripts.phase2_run_structural_search import load_reduced_path_matrix, sha256_path, write_catalog
from src.phase2_balanced_structural_search import generate_balanced_structural_scenarios


HUB_ID = "rail:S01514"
ALLOWED_V2_EVIDENCE = {
    "FACT_FROZEN_GATE_D_RAIL_ANCHOR",
    "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE",
    "DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID",
    "PROPOSED_STOP/FIELD_CHECK_PENDING",
}
ALLOWED_SOURCE_KINDS = {
    "HUB_RAIL",
    "EXISTING_PHYSICAL_STOP_CLUSTER",
    "PROPOSED_STOP",
}
EXPECTED_STATUS_BY_KIND = {
    "HUB_RAIL": {"FACT_FROZEN_GATE_D_RAIL_ANCHOR"},
    "EXISTING_PHYSICAL_STOP_CLUSTER": {
        "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE",
        "DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID",
    },
    "PROPOSED_STOP": {"PROPOSED_STOP/FIELD_CHECK_PENDING"},
}
FORBIDDEN_EVIDENCE = {"PLACEHOLDER", "INVALIDATED", "FACT", "DERIVED"}


def parse_bool(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def load_v2_anchor_universe(path: Path) -> tuple[list[str], dict[str, int], dict[str, int], str]:
    """Load the V2 routing universe without degrading its epistemic labels."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"anchor_id", "evidence_status", "enabled", "source_kind", "epoch_id"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"V2 anchor universe missing columns: {missing}")

        anchors: list[str] = []
        seen: set[str] = set()
        evidence_counts: Counter[str] = Counter()
        kind_counts: Counter[str] = Counter()
        epochs: set[str] = set()

        for line_no, row in enumerate(reader, start=2):
            if not parse_bool(row.get("enabled", "true")):
                continue
            anchor_id = str(row.get("anchor_id", "")).strip()
            evidence = str(row.get("evidence_status", "")).strip()
            source_kind = str(row.get("source_kind", "")).strip().upper()
            epoch_id = str(row.get("epoch_id", "")).strip()
            if not anchor_id:
                raise ValueError(f"V2 anchor universe line {line_no} has empty anchor_id")
            if anchor_id in seen:
                raise ValueError(f"Duplicate enabled V2 anchor_id: {anchor_id}")
            if evidence in FORBIDDEN_EVIDENCE or evidence not in ALLOWED_V2_EVIDENCE:
                raise ValueError(f"Anchor {anchor_id} has unsupported/degraded evidence state {evidence!r}")
            if source_kind not in ALLOWED_SOURCE_KINDS:
                raise ValueError(f"Anchor {anchor_id} has unsupported source_kind {source_kind!r}")
            if evidence not in EXPECTED_STATUS_BY_KIND[source_kind]:
                raise ValueError(
                    f"Anchor {anchor_id} evidence/source mismatch: {evidence!r} vs {source_kind!r}"
                )
            if not epoch_id:
                raise ValueError(f"Anchor {anchor_id} has empty frozen epoch_id")
            seen.add(anchor_id)
            anchors.append(anchor_id)
            evidence_counts[evidence] += 1
            kind_counts[source_kind] += 1
            epochs.add(epoch_id)

    if not anchors:
        raise ValueError("V2 anchor universe contains no enabled anchors")
    if len(epochs) != 1:
        raise ValueError(f"V2 anchor universe spans multiple frozen epochs: {sorted(epochs)}")
    if HUB_ID not in seen:
        raise ValueError(f"V2 anchor universe is missing required rail hub {HUB_ID}")
    return (
        sorted(anchors),
        dict(sorted(evidence_counts.items())),
        dict(sorted(kind_counts.items())),
        next(iter(epochs)),
    )


def validate_upstream_matrix_contract(
    validation_path: Path,
    *,
    anchor_path: Path,
    matrix_path: Path,
) -> dict:
    payload = json.loads(validation_path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced Path Matrix V2 upstream status is not PASS")
    if payload.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Unexpected Reduced Path Matrix V2 contract")
    if payload.get("hub_anchor_id") != HUB_ID:
        raise ValueError("Reduced Path Matrix V2 hub differs from the Phase 2 hub")
    prohibitions = payload.get("prohibitions", {})
    required_false = {
        "live_osm_used",
        "random_generation_used",
        "topology_selected",
        "proposed_stop_physically_certified",
        "context_gtfs_centroid_promoted_to_exact_fact_coordinate",
        "headway_or_timetable_selected",
        "budget_modified",
    }
    for key in sorted(required_false):
        if prohibitions.get(key) is not False:
            raise ValueError(f"Upstream prohibition {key!r} is not explicitly false")
    lineage = payload.get("lineage", {})
    if lineage.get("routing_anchor_universe_sha256") != sha256_path(anchor_path):
        raise ValueError("V2 routing-anchor universe hash does not match upstream validation")
    if lineage.get("reduced_path_matrix_sha256") != sha256_path(matrix_path):
        raise ValueError("V2 reduced-path matrix hash does not match upstream validation")
    return payload


def write_v2_validation(
    path: Path,
    *,
    upstream_validation_path: Path,
    upstream_validation: dict,
    anchor_path: Path,
    matrix_path: Path,
    output_path: Path,
    source_anchors: list[str],
    structural_anchors: list[str],
    excluded_anchors: list[str],
    evidence_counts: dict[str, int],
    kind_counts: dict[str, int],
    epoch_id: str,
    result,
    max_scenarios: int,
    max_loop_intermediate_anchors: int,
) -> None:
    payload = {
        "status": "PASS_STRUCTURAL_CATALOG_V2_BUILD",
        "contract": "PHASE2_BALANCED_STRUCTURAL_SEARCH_V2",
        "evidence_label": "V2_STRUCTURAL_CATALOG_NOT_RECOMMENDATION",
        "hub_anchor_id": HUB_ID,
        "epoch_id": epoch_id,
        "source_routing_anchor_count": len(source_anchors),
        "source_kind_counts": kind_counts,
        "source_evidence_status_counts": evidence_counts,
        "hub_bidirectional_structural_anchor_count": len(structural_anchors),
        "hub_bidirectional_nonhub_anchor_count": len(structural_anchors) - 1,
        "excluded_non_bidirectional_anchor_count": len(excluded_anchors),
        "excluded_non_bidirectional_anchor_ids": excluded_anchors,
        "requested_scenario_count": max_scenarios,
        "generated_scenario_count": len(result.scenarios),
        "max_loop_intermediate_anchors": max_loop_intermediate_anchors,
        "allocation_rule": result.allocation_rule,
        "valid_single_radial_count": result.valid_radial_count,
        "family_targets": dict(result.family_targets),
        "family_counts": dict(result.family_counts),
        "exhausted_families": list(result.exhausted_families),
        "deterministic": True,
        "uses_live_osm": False,
        "uses_random_generation": False,
        "uses_legacy_candidate_routes": False,
        "uses_topology_preference_score": False,
        "search_allocation_is_decision_weight": False,
        "selects_topology": False,
        "selects_stops": False,
        "chooses_service_policy": False,
        "lineage": {
            "upstream_matrix_validation": str(upstream_validation_path),
            "upstream_matrix_validation_sha256": sha256_path(upstream_validation_path),
            "upstream_matrix_contract": upstream_validation["contract"],
            "upstream_matrix_epoch_id": upstream_validation["epoch_id"],
            "routing_anchor_universe": str(anchor_path),
            "routing_anchor_universe_sha256": sha256_path(anchor_path),
            "reduced_path_matrix": str(matrix_path),
            "reduced_path_matrix_sha256": sha256_path(matrix_path),
            "scenario_catalog": str(output_path),
            "scenario_catalog_sha256": sha256_path(output_path),
        },
        "epistemic_note": (
            "This catalog replays the audited family-balanced structural search on the V2 routing "
            "universe and matrix. Detailed V2 evidence labels are preserved and validated. Equal-family "
            "allocation controls search coverage only and is not a decision weight or recommendation."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--path-matrix", required=True, type=Path)
    parser.add_argument("--upstream-validation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--max-scenarios", type=int, default=100_000)
    parser.add_argument("--max-loop-intermediate-anchors", type=int, default=4)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for path in (args.anchors, args.path_matrix, args.upstream_validation):
        if not path.is_file():
            raise FileNotFoundError(path)
    upstream = validate_upstream_matrix_contract(
        args.upstream_validation,
        anchor_path=args.anchors,
        matrix_path=args.path_matrix,
    )
    anchors, evidence_counts, kind_counts, epoch_id = load_v2_anchor_universe(args.anchors)
    if len(anchors) != int(upstream["routing_anchor_count"]):
        raise ValueError("V2 routing-anchor count differs from upstream matrix validation")
    if epoch_id != str(upstream["epoch_id"]):
        raise ValueError("V2 anchor epoch differs from upstream matrix epoch")

    matrix = load_reduced_path_matrix(args.path_matrix)
    structural_anchors, excluded = hub_bidirectional_anchor_filter(
        hub=HUB_ID,
        anchors=anchors,
        matrix=matrix,
    )
    result = generate_balanced_structural_scenarios(
        hub=HUB_ID,
        anchors=structural_anchors,
        matrix=matrix,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    if not result.scenarios:
        raise RuntimeError("V2 balanced structural search generated no scenarios")
    write_catalog(args.output, result.scenarios)
    write_v2_validation(
        args.validation,
        upstream_validation_path=args.upstream_validation,
        upstream_validation=upstream,
        anchor_path=args.anchors,
        matrix_path=args.path_matrix,
        output_path=args.output,
        source_anchors=anchors,
        structural_anchors=structural_anchors,
        excluded_anchors=excluded,
        evidence_counts=evidence_counts,
        kind_counts=kind_counts,
        epoch_id=epoch_id,
        result=result,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    print(
        f"generated {len(result.scenarios)} V2 family-balanced scenarios from "
        f"{len(structural_anchors)} hub-bidirectional anchors -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
