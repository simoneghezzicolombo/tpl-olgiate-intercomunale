#!/usr/bin/env python3
"""Build frequency-capability structural frontiers for the Phase 2 tournament.

This stage answers a narrow but important pre-final question: which structural
scenarios remain non-dominated on resident access, worst-municipality access and
territorial work-OD addressability once we require that at least one *joint*
service plan (headway/span/calendar/extension share, robust across all declared
recovery sensitivities) fits a given annual bus-km envelope?

It does not select a service plan, timetable, S8 phase, topology, PRIMARY or
RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_pretournament_structural_frontier_v2 import MetricPoint, nondominated_metric_points

CONTRACT = "PHASE2_FREQUENCY_CAPABILITY_FRONTIERS_V2"
STATUS = "PASS_FREQUENCY_CAPABILITY_FRONTIERS_V2_BUILD"
BUDGET_SUFFIXES = ("m20pct", "m10pct", "reference", "p10pct", "p20pct", "p30pct")
HEADWAY_THRESHOLDS = (15, 20, 30, 60)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_csv(path: Path):
    return gzip.open(path, "rt", encoding="utf-8-sig", newline="") if path.suffix == ".gz" else path.open("r", encoding="utf-8-sig", newline="")


def load_scenario_rows(path: Path, required: set[str], label: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with open_csv(path) as f:
        r = csv.DictReader(f)
        missing = required - set(r.fieldnames or [])
        if missing:
            raise ValueError(f"{label} missing columns {sorted(missing)}")
        for line_no, row in enumerate(r, 2):
            sid = str(row["scenario_id"]).strip()
            if not sid or sid in rows:
                raise ValueError(f"{label} invalid/duplicate scenario at line {line_no}")
            rows[sid] = row
    if len(rows) != 100000:
        raise ValueError(f"{label} expected 100000 scenarios, got {len(rows)}")
    return rows


def load_policy_groups(path: Path):
    groups: dict[tuple[int, str, str, float], dict[int, int]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {"policy_index", "uniform_headway_min", "span_id", "calendar_id", "recovery_min", "extension_share"}
        if not required <= set(r.fieldnames or []):
            raise ValueError("Policy grid schema mismatch")
        for row in r:
            idx = int(row["policy_index"])
            key = (
                int(row["uniform_headway_min"]),
                str(row["span_id"]),
                str(row["calendar_id"]),
                float(row["extension_share"]),
            )
            recovery = int(row["recovery_min"])
            if recovery in groups[key]:
                raise ValueError(f"Duplicate recovery {recovery} for plan {key}")
            groups[key][recovery] = idx
    if len(groups) != 96:
        raise ValueError(f"Expected 96 passenger-facing service-plan signatures, got {len(groups)}")
    out = []
    for key, by_recovery in sorted(groups.items()):
        if set(by_recovery) != {5, 10, 15}:
            raise ValueError(f"Plan {key} does not contain all recovery sensitivities")
        mask = 0
        for idx in by_recovery.values():
            mask |= 1 << idx
        out.append((key, mask))
    return out


def robust_plan_masks(policy_groups, *, family: str, max_headway: int):
    masks = []
    for (headway, span_id, calendar_id, extension_share), mask in policy_groups:
        if headway > max_headway:
            continue
        if family != "scheduled_extensions" and abs(extension_share) > 1e-12:
            continue
        masks.append(mask)
    return masks


def any_complete_group(feasible_mask: int, group_masks: list[int]) -> bool:
    return any((feasible_mask & group_mask) == group_mask for group_mask in group_masks)


def validate_upstream(args):
    av = loadj(args.access_validation)
    tv = loadj(args.territorial_validation)
    sv = loadj(args.service_validation)
    if av.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or av.get("lineage", {}).get("scenario_output_sha256") != sha(args.access):
        raise ValueError("Access/Equity V2 not certified")
    if tv.get("status") != "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD" or tv.get("lineage", {}).get("scenario_output_sha256") != sha(args.territorial):
        raise ValueError("Territorial V2 not certified")
    if sv.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD" or sv.get("lineage", {}).get("feasibility_output_sha256") != sha(args.service_feasibility):
        raise ValueError("Service Policy Search V2 not certified")
    if sv.get("lineage", {}).get("policy_grid_sha256") != sha(args.policy_grid):
        raise ValueError("Service policy grid hash mismatch")
    if int(sv.get("scenario_count", -1)) != 100000:
        raise ValueError("Unexpected service scenario count")
    caps = [float(v) for v in sv.get("budget_caps_annual_bus_km", [])]
    if len(caps) != 6 or abs(caps[2] - 111419.0) > 1e-9:
        raise ValueError("Unexpected budget envelopes")
    return av, tv, sv, caps


ACCESS_REQ = {
    "scenario_id", "topology_family", "public_population_covered_10min",
    "public_population_coverage_share_10min", "public_worst_municipality_10min",
    "public_worst_municipality_coverage_share_10min",
}
TERR_REQ = {
    "scenario_id", "topology_family", "public_structurally_addressable_od_relation_count",
    "public_structurally_addressable_worker_od_mass_upper_bound",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--access", type=Path, required=True)
    p.add_argument("--access-validation", type=Path, required=True)
    p.add_argument("--territorial", type=Path, required=True)
    p.add_argument("--territorial-validation", type=Path, required=True)
    p.add_argument("--service-feasibility", type=Path, required=True)
    p.add_argument("--service-validation", type=Path, required=True)
    p.add_argument("--policy-grid", type=Path, required=True)
    p.add_argument("--frontier-output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    av, tv, sv, caps = validate_upstream(args)
    access = load_scenario_rows(args.access, ACCESS_REQ, "access")
    territorial = load_scenario_rows(args.territorial, TERR_REQ, "territorial")
    if set(access) != set(territorial):
        raise ValueError("Access and territorial scenario sets differ")
    policy_groups = load_policy_groups(args.policy_grid)

    points: dict[str, MetricPoint] = {}
    families: dict[str, str] = {}
    descriptive: dict[str, tuple[str, str, str]] = {}
    for sid in access:
        a, t = access[sid], territorial[sid]
        if a["topology_family"] != t["topology_family"]:
            raise ValueError(f"Family mismatch for {sid}")
        families[sid] = a["topology_family"]
        points[sid] = MetricPoint.from_values(
            a["public_population_coverage_share_10min"],
            a["public_worst_municipality_coverage_share_10min"],
            t["public_structurally_addressable_worker_od_mass_upper_bound"],
        )
        descriptive[sid] = (
            a["public_population_covered_10min"],
            a["public_worst_municipality_10min"],
            t["public_structurally_addressable_od_relation_count"],
        )

    combo_index = {(budget, hw): i for i, (budget, hw) in enumerate((b, h) for b in BUDGET_SUFFIXES for h in HEADWAY_THRESHOLDS)}
    eligibility_bits: dict[str, int] = {}
    eligible_counts = Counter()

    group_cache = {
        (family, hw): robust_plan_masks(policy_groups, family=family, max_headway=hw)
        for family in set(families.values()) for hw in HEADWAY_THRESHOLDS
    }

    with gzip.open(args.service_feasibility, "rt", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {"scenario_id", "topology_family"} | {f"feasible_policy_mask_hex_{b}" for b in BUDGET_SUFFIXES}
        if not required <= set(r.fieldnames or []):
            raise ValueError("Service feasibility schema mismatch")
        service_ids = set()
        for row in r:
            sid = row["scenario_id"]
            if sid not in points or sid in service_ids:
                raise ValueError(f"Service scenario mismatch/duplicate {sid}")
            service_ids.add(sid)
            family = row["topology_family"]
            if family != families[sid]:
                raise ValueError(f"Service family mismatch for {sid}")
            bits = 0
            for budget in BUDGET_SUFFIXES:
                feasible_mask = int(row[f"feasible_policy_mask_hex_{budget}"], 16)
                for hw in HEADWAY_THRESHOLDS:
                    if any_complete_group(feasible_mask, group_cache[(family, hw)]):
                        idx = combo_index[(budget, hw)]
                        bits |= 1 << idx
                        eligible_counts[(budget, hw)] += 1
            eligibility_bits[sid] = bits
    if set(eligibility_bits) != set(points):
        raise ValueError("Service scenario set differs from structural inputs")

    frontier_points: dict[tuple[str, int], frozenset[MetricPoint]] = {}
    frontier_ids: dict[tuple[str, int], list[str]] = {}
    for combo, idx in combo_index.items():
        pts = [points[sid] for sid, bits in eligibility_bits.items() if bits & (1 << idx)]
        fp = nondominated_metric_points(pts)
        frontier_points[combo] = fp
        frontier_ids[combo] = [sid for sid, bits in eligibility_bits.items() if bits & (1 << idx) and points[sid] in fp]

    fields = [
        "budget_suffix", "annual_bus_km_cap", "max_headway_min", "scenario_id", "topology_family",
        "public_population_covered_10min", "public_population_coverage_share_10min",
        "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
        "public_structurally_addressable_od_relation_count", "public_structurally_addressable_worker_od_mass_upper_bound",
        "frequency_capability_frontier", "service_policy_selected", "topology_selected", "s8_phase_selected",
    ]
    args.frontier_output.parent.mkdir(parents=True, exist_ok=True)
    with args.frontier_output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for b_idx, budget in enumerate(BUDGET_SUFFIXES):
            for hw in HEADWAY_THRESHOLDS:
                for sid in sorted(frontier_ids[(budget, hw)]):
                    point = points[sid]
                    pop, worst_name, od_rel = descriptive[sid]
                    w.writerow({
                        "budget_suffix": budget,
                        "annual_bus_km_cap": f"{caps[b_idx]:.6f}",
                        "max_headway_min": hw,
                        "scenario_id": sid,
                        "topology_family": families[sid],
                        "public_population_covered_10min": pop,
                        "public_population_coverage_share_10min": str(point.population_coverage_share_10min),
                        "public_worst_municipality_10min": worst_name,
                        "public_worst_municipality_coverage_share_10min": str(point.worst_municipality_coverage_share_10min),
                        "public_structurally_addressable_od_relation_count": od_rel,
                        "public_structurally_addressable_worker_od_mass_upper_bound": str(point.territorial_worker_od_mass_upper_bound),
                        "frequency_capability_frontier": "true",
                        "service_policy_selected": "false",
                        "topology_selected": "false",
                        "s8_phase_selected": "false",
                    })

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "scenario_count": 100000,
        "reference_budget_bus_km_year": caps[2],
        "headway_thresholds_min": list(HEADWAY_THRESHOLDS),
        "budget_suffixes": list(BUDGET_SUFFIXES),
        "eligible_scenario_counts": {f"{b}__h{h}": eligible_counts[(b, h)] for b in BUDGET_SUFFIXES for h in HEADWAY_THRESHOLDS},
        "frontier_scenario_counts": {f"{b}__h{h}": len(frontier_ids[(b, h)]) for b in BUDGET_SUFFIXES for h in HEADWAY_THRESHOLDS},
        "frontier_unique_metric_point_counts": {f"{b}__h{h}": len(frontier_points[(b, h)]) for b in BUDGET_SUFFIXES for h in HEADWAY_THRESHOLDS},
        "reference_family_counts": {f"h{h}": dict(sorted(Counter(families[sid] for sid in frontier_ids[("reference", h)]).items())) for h in HEADWAY_THRESHOLDS},
        "recovery_semantics": "ROBUST_PASSENGER_FACING_PLAN_REQUIRES_ALL_5_10_15_MIN_RECOVERY_POLICY_VARIANTS_WITHIN_BUDGET",
        "weighted_composite_score_used": False,
        "service_policy_selected": False,
        "topology_selected": False,
        "s8_feeder_metric_used": False,
        "s8_phase_selected": False,
        "full_passenger_gjt_calculated": False,
        "scheduled_extension_note": "This frontier uses base-public structural metrics only. Extension-specific accessibility remains separate until an explicit extension timetable is constructed.",
        "lineage": {
            "access_sha256": sha(args.access),
            "access_validation_sha256": sha(args.access_validation),
            "territorial_sha256": sha(args.territorial),
            "territorial_validation_sha256": sha(args.territorial_validation),
            "service_feasibility_sha256": sha(args.service_feasibility),
            "service_validation_sha256": sha(args.service_validation),
            "policy_grid_sha256": sha(args.policy_grid),
            "frontier_output_sha256": sha(args.frontier_output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
