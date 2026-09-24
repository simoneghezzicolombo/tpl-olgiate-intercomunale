#!/usr/bin/env python3
"""Materialise a conservative current-service continuity surface for Phase 2.

This stage measures only continuity that is provable from the certified localisable
D184/D185 current-service lower bound. It never infers unresolved current stops,
never treats the project station bridge as the historical current station identity,
and never converts geometric proximity into stop retention.

Outputs are descriptive/tie-break evidence only. No candidate is selected or
eliminated by this stage.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

STATUS = "PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2"
CONTRACT = "PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def explicit_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false, got {value!r}")


def validate_upstream(args) -> tuple[dict, dict, dict, dict]:
    current = read_json(args.current_validation)
    matrix = read_json(args.matrix_validation)
    s8 = read_json(args.s8_validation)
    passenger = read_json(args.passenger_validation)

    if current.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V2":
        raise ValueError("Certified current-service lower-bound validation is required")
    if current.get("contract") != "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V2":
        raise ValueError("Unexpected current-service baseline contract")
    if current.get("baseline_complete") is not False or current.get("may_infer_true_current_total_coverage") is not False:
        raise ValueError("Current baseline must remain explicitly incomplete")
    if current.get("may_use_unresolved_rows_for_spatial_access") is not False:
        raise ValueError("Unresolved current stops may not be spatially used")
    if current.get("historical_station_identity_kept_separate_from_project_hub_bridge") is not True:
        raise ValueError("Historical station identity must remain separate from project hub bridge")
    if current.get("historical_station_stop_id") != "300407":
        raise ValueError("Unexpected historical station stop identity")
    if current.get("project_station_access_cluster") != "EX_039" or current.get("project_station_access_stop_id") != "L00407":
        raise ValueError("Unexpected project station bridge identity")
    if current.get("lineage", {}).get("localized_output_sha256") != sha256_path(args.current_localized):
        raise ValueError("Current-service localised-row hash mismatch")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Certified reduced-path-matrix validation is required")
    if matrix.get("lineage", {}).get("routing_anchor_universe_sha256") != sha256_path(args.routing_anchors):
        raise ValueError("Routing anchor universe hash mismatch")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Certified S8 V2 route/mapping lineage is required")
    if s8.get("lineage", {}).get("route_universe_sha256") != sha256_path(args.route_universe):
        raise ValueError("S8 route-universe hash mismatch")
    if s8.get("lineage", {}).get("scenario_route_mapping_sha256") != sha256_path(args.scenario_mapping):
        raise ValueError("S8 scenario-mapping hash mismatch")

    if passenger.get("status") != "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Certified Passenger Utility Frontier V2 is required")
    if passenger.get("contract") != "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Unexpected Passenger Utility contract")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger Utility frontier hash mismatch")
    if int(passenger.get("passenger_utility_frontier_row_count_all_budgets", -1)) != 16883:
        raise ValueError("Unexpected Passenger Utility frontier row count")
    if passenger.get("primary_selected") is not False or passenger.get("runner_up_selected") is not False:
        raise ValueError("Passenger upstream already contains forbidden final selection")
    return current, matrix, s8, passenger


def derive_current_lower_bound(rows: list[dict[str, str]], current_validation: dict):
    required = {
        "route_id", "source_page", "stop_sequence_on_page", "v2_physical_cluster_id", "localization_status"
    }
    if not rows or not required <= set(rows[0]):
        raise ValueError("Current-service localised rows have invalid schema")

    localized_status = "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"
    localized_rows = [r for r in rows if r.get("localization_status") == localized_status]
    clusters = sorted({str(r["v2_physical_cluster_id"]).strip() for r in localized_rows})
    expected = sorted(str(x) for x in current_validation.get("localized_unique_physical_clusters", []))
    if clusters != expected:
        raise ValueError(f"Current localisable clusters disagree with validation: {clusters} != {expected}")
    if len(localized_rows) != int(current_validation.get("localized_rows", -1)):
        raise ValueError("Current localisable-row count mismatch")
    if len(clusters) != int(current_validation.get("localized_unique_physical_cluster_count", -1)):
        raise ValueError("Current localisable-cluster count mismatch")

    by_route: dict[str, set[str]] = defaultdict(set)
    for row in localized_rows:
        by_route[str(row["route_id"])].add(str(row["v2_physical_cluster_id"]).strip())

    directed_pairs: set[tuple[str, str]] = set()
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["route_id"]), int(row["source_page"]))].append(row)
    for _, group in grouped.items():
        ordered = sorted(group, key=lambda r: int(r["stop_sequence_on_page"]))
        for a, b in zip(ordered[:-1], ordered[1:]):
            if int(b["stop_sequence_on_page"]) != int(a["stop_sequence_on_page"]) + 1:
                raise ValueError("Current PDF stop sequence is non-consecutive within page")
            if a.get("localization_status") != localized_status or b.get("localization_status") != localized_status:
                continue
            ca = str(a["v2_physical_cluster_id"]).strip()
            cb = str(b["v2_physical_cluster_id"]).strip()
            if ca and cb and ca != cb:
                directed_pairs.add((ca, cb))
    undirected_pairs = {tuple(sorted(pair)) for pair in directed_pairs}
    return clusters, dict(by_route), sorted(directed_pairs), sorted(undirected_pairs)


def build_cluster_anchor_map(path: Path, current_clusters: list[str], matrix_validation: dict) -> dict[str, str]:
    rows = read_csv(path)
    if len(rows) != int(matrix_validation.get("routing_anchor_count", -1)):
        raise ValueError("Routing-anchor row count mismatch")
    by_member: dict[str, str] = {}
    for row in rows:
        anchor_id = str(row["anchor_id"]).strip()
        for member in str(row.get("source_members", "")).split(";"):
            member = member.strip()
            if member:
                if member in by_member and by_member[member] != anchor_id:
                    raise ValueError(f"Routing source member occurs in multiple anchors: {member}")
                by_member[member] = anchor_id
    result: dict[str, str] = {}
    for cluster in current_clusters:
        member = f"existing:{cluster}"
        try:
            result[cluster] = by_member[member]
        except KeyError as exc:
            raise ValueError(f"Current localisable cluster missing from routing universe: {cluster}") from exc
    # Project bridge must not masquerade as the historical station cluster.
    if result.get("EX_011") == by_member.get("existing:EX_039"):
        raise ValueError("Historical station EX_011 collapsed into project bridge EX_039")
    return result


def load_route_anchors(path: Path, s8_validation: dict) -> dict[str, tuple[str, ...]]:
    rows = read_csv(path)
    if len(rows) != int(s8_validation.get("unique_route_count", -1)):
        raise ValueError("Route-universe row count mismatch")
    out: dict[str, tuple[str, ...]] = {}
    for row in rows:
        route_id = str(row["route_id"])
        if route_id in out:
            raise ValueError(f"Duplicate route_id {route_id}")
        anchors_raw = json.loads(row["anchors_json"])
        if not isinstance(anchors_raw, list) or len(anchors_raw) < 2:
            raise ValueError(f"Invalid public route anchors for {route_id}")
        anchors = tuple(str(x) for x in anchors_raw)
        if anchors[0] != "rail:S01514":
            raise ValueError(f"Route {route_id} does not start at certified rail hub")
        out[route_id] = anchors
    return out


def scenario_continuity(
    *,
    scenario_id: str,
    topology_family: str,
    route_ids: list[str],
    route_anchors: dict[str, tuple[str, ...]],
    current_clusters: list[str],
    cluster_anchor: dict[str, str],
    route_current_clusters: dict[str, set[str]],
    current_directed_pairs: list[tuple[str, str]],
    current_undirected_pairs: list[tuple[str, str]],
) -> dict[str, object]:
    if not route_ids:
        raise ValueError(f"Scenario {scenario_id} has no public routes")
    anchor_union: set[str] = set()
    candidate_directed_pairs: set[tuple[str, str]] = set()
    candidate_undirected_pairs: set[tuple[str, str]] = set()
    for route_id in route_ids:
        try:
            anchors = route_anchors[route_id]
        except KeyError as exc:
            raise ValueError(f"Scenario {scenario_id} references unknown public route {route_id}") from exc
        anchor_union.update(anchors)
        for a, b in zip(anchors[:-1], anchors[1:]):
            candidate_directed_pairs.add((a, b))
            candidate_undirected_pairs.add(tuple(sorted((a, b))))

    retained_clusters = [c for c in current_clusters if cluster_anchor[c] in anchor_union]
    omitted_clusters = [c for c in current_clusters if c not in retained_clusters]

    retained_directed = [
        pair for pair in current_directed_pairs
        if (cluster_anchor[pair[0]], cluster_anchor[pair[1]]) in candidate_directed_pairs
    ]
    retained_undirected = [
        pair for pair in current_undirected_pairs
        if tuple(sorted((cluster_anchor[pair[0]], cluster_anchor[pair[1]]))) in candidate_undirected_pairs
    ]

    out: dict[str, object] = {
        "scenario_id": scenario_id,
        "topology_family": topology_family,
        "public_route_count": len(route_ids),
        "current_localizable_cluster_count": len(current_clusters),
        "retained_current_localizable_cluster_count": len(retained_clusters),
        "retained_current_localizable_cluster_share": len(retained_clusters) / len(current_clusters),
        "omitted_current_localizable_cluster_count": len(omitted_clusters),
        "retained_current_localizable_clusters_json": json.dumps(retained_clusters, separators=(",", ":")),
        "omitted_current_localizable_clusters_json": json.dumps(omitted_clusters, separators=(",", ":")),
        "current_localizable_directed_adjacent_pair_count": len(current_directed_pairs),
        "retained_current_localizable_directed_adjacent_pair_count": len(retained_directed),
        "retained_current_localizable_directed_adjacent_pair_share": (
            len(retained_directed) / len(current_directed_pairs) if current_directed_pairs else 1.0
        ),
        "current_localizable_undirected_adjacent_pair_count": len(current_undirected_pairs),
        "retained_current_localizable_undirected_adjacent_pair_count": len(retained_undirected),
        "retained_current_localizable_undirected_adjacent_pair_share": (
            len(retained_undirected) / len(current_undirected_pairs) if current_undirected_pairs else 1.0
        ),
        "retained_current_directed_pairs_json": json.dumps(retained_directed, separators=(",", ":")),
        "retained_current_undirected_pairs_json": json.dumps(retained_undirected, separators=(",", ":")),
        "historical_station_cluster_EX_011_retained": "true" if "EX_011" in retained_clusters else "false",
        "project_station_bridge_EX_039_counts_as_current_continuity": "false",
        "continuity_is_complete_current_service_measure": "false",
        "unresolved_current_rows_inferred": "false",
        "proximity_used_as_stop_retention": "false",
        "candidate_eliminated_by_continuity": "false",
    }
    for route_id in sorted(route_current_clusters):
        clusters = route_current_clusters[route_id]
        retained = sorted(clusters.intersection(retained_clusters))
        key = route_id.lower()
        out[f"{key}_current_localizable_cluster_count"] = len(clusters)
        out[f"{key}_retained_localizable_cluster_count"] = len(retained)
        out[f"{key}_retained_localizable_cluster_share"] = len(retained) / len(clusters) if clusters else 1.0
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current-localized", type=Path, required=True)
    p.add_argument("--current-validation", type=Path, required=True)
    p.add_argument("--routing-anchors", type=Path, required=True)
    p.add_argument("--matrix-validation", type=Path, required=True)
    p.add_argument("--route-universe", type=Path, required=True)
    p.add_argument("--scenario-mapping", type=Path, required=True)
    p.add_argument("--s8-validation", type=Path, required=True)
    p.add_argument("--passenger-frontier", type=Path, required=True)
    p.add_argument("--passenger-validation", type=Path, required=True)
    p.add_argument("--scenario-output", type=Path, required=True)
    p.add_argument("--plan-output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    current, matrix, s8, passenger = validate_upstream(args)
    current_rows = read_csv(args.current_localized)
    current_clusters, route_current_clusters, directed_pairs, undirected_pairs = derive_current_lower_bound(current_rows, current)
    cluster_anchor = build_cluster_anchor_map(args.routing_anchors, current_clusters, matrix)
    route_anchors = load_route_anchors(args.route_universe, s8)

    scenario_fields = [
        "scenario_id", "topology_family", "public_route_count",
        "current_localizable_cluster_count", "retained_current_localizable_cluster_count",
        "retained_current_localizable_cluster_share", "omitted_current_localizable_cluster_count",
        "retained_current_localizable_clusters_json", "omitted_current_localizable_clusters_json",
        "current_localizable_directed_adjacent_pair_count", "retained_current_localizable_directed_adjacent_pair_count",
        "retained_current_localizable_directed_adjacent_pair_share",
        "current_localizable_undirected_adjacent_pair_count", "retained_current_localizable_undirected_adjacent_pair_count",
        "retained_current_localizable_undirected_adjacent_pair_share",
        "retained_current_directed_pairs_json", "retained_current_undirected_pairs_json",
        "historical_station_cluster_EX_011_retained", "project_station_bridge_EX_039_counts_as_current_continuity",
        "d184_current_localizable_cluster_count", "d184_retained_localizable_cluster_count", "d184_retained_localizable_cluster_share",
        "d185_current_localizable_cluster_count", "d185_retained_localizable_cluster_count", "d185_retained_localizable_cluster_share",
        "continuity_is_complete_current_service_measure", "unresolved_current_rows_inferred",
        "proximity_used_as_stop_retention", "candidate_eliminated_by_continuity",
    ]
    scenario_lookup: dict[str, dict[str, object]] = {}
    raw_s, text_s, writer_s = deterministic_gzip_writer(args.scenario_output, scenario_fields)
    try:
        for row in read_gzip_csv(args.scenario_mapping):
            sid = str(row["scenario_id"])
            if sid in scenario_lookup:
                raise ValueError(f"Duplicate scenario mapping {sid}")
            route_ids_raw = json.loads(row["public_route_ids_json"])
            if not isinstance(route_ids_raw, list):
                raise ValueError(f"Scenario {sid} public_route_ids_json is not a list")
            out = scenario_continuity(
                scenario_id=sid,
                topology_family=str(row["topology_family"]),
                route_ids=[str(x) for x in route_ids_raw],
                route_anchors=route_anchors,
                current_clusters=current_clusters,
                cluster_anchor=cluster_anchor,
                route_current_clusters=route_current_clusters,
                current_directed_pairs=directed_pairs,
                current_undirected_pairs=undirected_pairs,
            )
            scenario_lookup[sid] = out
            writer_s.writerow(out)
    finally:
        text_s.close()
        raw_s.close()
    if len(scenario_lookup) != int(s8.get("scenario_count", -1)) or len(scenario_lookup) != 100000:
        raise ValueError(f"Unexpected scenario continuity count {len(scenario_lookup)}")

    plan_fields = [
        "plan_id", "scenario_id", "budget_suffix", "uniform_headway_min", "span_id", "calendar_id",
        *[field for field in scenario_fields if field not in {"scenario_id", "topology_family", "public_route_count"}],
        "topology_family", "public_route_count",
    ]
    plan_count = 0
    plan_scenarios: set[str] = set()
    budget_counts: dict[str, int] = defaultdict(int)
    retention_counts: dict[str, int] = defaultdict(int)
    raw_p, text_p, writer_p = deterministic_gzip_writer(args.plan_output, plan_fields)
    try:
        for plan in read_gzip_csv(args.passenger_frontier):
            sid = str(plan["scenario_id"])
            try:
                continuity = scenario_lookup[sid]
            except KeyError as exc:
                raise ValueError(f"Passenger plan references unknown scenario {sid}") from exc
            out = {
                "plan_id": str(plan["plan_id"]),
                "scenario_id": sid,
                "budget_suffix": str(plan["budget_suffix"]),
                "uniform_headway_min": int(plan["uniform_headway_min"]),
                "span_id": str(plan["span_id"]),
                "calendar_id": str(plan["calendar_id"]),
                **continuity,
            }
            writer_p.writerow(out)
            plan_count += 1
            plan_scenarios.add(sid)
            budget_counts[str(plan["budget_suffix"])] += 1
            retention_counts[str(continuity["retained_current_localizable_cluster_count"])] += 1
    finally:
        text_p.close()
        raw_p.close()
    if plan_count != int(passenger["passenger_utility_frontier_row_count_all_budgets"]):
        raise ValueError(f"Passenger continuity plan count mismatch: {plan_count}")

    scenario_retained_counts = [int(r["retained_current_localizable_cluster_count"]) for r in scenario_lookup.values()]
    scenario_directed_counts = [int(r["retained_current_localizable_directed_adjacent_pair_count"]) for r in scenario_lookup.values()]
    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "baseline_role": "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY",
        "current_localizable_row_count": int(current["localized_rows"]),
        "current_unresolved_or_unlocalized_row_count": int(current["unresolved_or_unlocalized_rows"]),
        "current_localizable_cluster_count": len(current_clusters),
        "current_localizable_clusters": current_clusters,
        "current_cluster_to_routing_anchor": cluster_anchor,
        "current_route_localizable_clusters": {k: sorted(v) for k, v in sorted(route_current_clusters.items())},
        "current_localizable_directed_adjacent_pairs": directed_pairs,
        "current_localizable_undirected_adjacent_pairs": undirected_pairs,
        "scenario_count": len(scenario_lookup),
        "passenger_utility_plan_count": plan_count,
        "passenger_utility_unique_scenario_count": len(plan_scenarios),
        "passenger_plan_budget_counts": dict(sorted(budget_counts.items())),
        "passenger_plan_retained_cluster_count_distribution": dict(sorted(retention_counts.items(), key=lambda kv: int(kv[0]))),
        "scenario_retained_current_cluster_count_min": min(scenario_retained_counts),
        "scenario_retained_current_cluster_count_max": max(scenario_retained_counts),
        "scenario_retained_current_directed_pair_count_min": min(scenario_directed_counts),
        "scenario_retained_current_directed_pair_count_max": max(scenario_directed_counts),
        "continuity_is_complete_current_service_measure": False,
        "unresolved_current_rows_inferred": False,
        "proximity_used_as_stop_retention": False,
        "historical_station_EX_011_kept_separate_from_project_bridge_EX_039": True,
        "project_station_bridge_counts_as_current_stop_retention": False,
        "continuity_used_to_eliminate_candidate": False,
        "continuity_used_to_select_primary": False,
        "continuity_used_to_select_runner_up": False,
        "weighted_composite_score": False,
        "epistemic_note": (
            "Continuity is measured only against current D184/D185 stop identities that the certified lower-bound "
            "baseline can localise exactly into Stop Universe V2. Stop retention requires exact routing-anchor identity; "
            "nearby proposed stops do not count. Corridor continuity uses only immediately consecutive current PDF rows "
            "whose two endpoints are both exactly localised; no pair is inferred across an unresolved row. Therefore all "
            "reported continuity metrics are conservative lower-bound descriptors suitable for a downstream practical "
            "tie-break, not a complete reconstruction of current service continuity."
        ),
        "lineage": {
            "current_localized": str(args.current_localized),
            "current_localized_sha256": sha256_path(args.current_localized),
            "current_validation": str(args.current_validation),
            "current_validation_sha256": sha256_path(args.current_validation),
            "routing_anchors": str(args.routing_anchors),
            "routing_anchors_sha256": sha256_path(args.routing_anchors),
            "matrix_validation": str(args.matrix_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "route_universe": str(args.route_universe),
            "route_universe_sha256": sha256_path(args.route_universe),
            "scenario_mapping": str(args.scenario_mapping),
            "scenario_mapping_sha256": sha256_path(args.scenario_mapping),
            "s8_validation": str(args.s8_validation),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "passenger_frontier": str(args.passenger_frontier),
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "passenger_validation": str(args.passenger_validation),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "scenario_output": str(args.scenario_output),
            "scenario_output_sha256": sha256_path(args.scenario_output),
            "plan_output": str(args.plan_output),
            "plan_output_sha256": sha256_path(args.plan_output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": STATUS,
        "scenario_count": report["scenario_count"],
        "passenger_utility_plan_count": report["passenger_utility_plan_count"],
        "current_localizable_cluster_count": report["current_localizable_cluster_count"],
        "current_localizable_directed_adjacent_pairs": report["current_localizable_directed_adjacent_pairs"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
