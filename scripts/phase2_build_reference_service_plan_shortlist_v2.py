#!/usr/bin/env python3
"""Build the reference-budget Phase 2 service-plan shortlist V2.

The shortlist is built from the complete reference-feasible scenario universe.
For each *identical passenger-facing service policy* (headway, span, calendar and
extension share), it retains structural Pareto scenarios. Recovery 5/10/15 is a
robustness sensitivity of the same plan, so a plan is eligible only when all
three recovery variants fit the 111,419 bus-km/year reference envelope.

For scheduled extensions, the shortlist is the union of a conservative
base-public frontier and an all-extension-anchors upper-bound frontier. The
upper bound is preserved explicitly and is never treated as realised service.

The output attaches joint plan resource calculations and the certified
route-unweighted S8 timing envelope at the same headway/span. It does NOT choose
a common S8 phase, construct an exact timetable, rank topology families, or
select PRIMARY/RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_pretournament_structural_frontier_v2 import MetricPoint, nondominated_metric_points
from src.phase2_service_plan_tournament_v2 import ServicePlanKey

STATUS = "PASS_REFERENCE_SERVICE_PLAN_SHORTLIST_V2_BUILD"
CONTRACT = "PHASE2_REFERENCE_SERVICE_PLAN_SHORTLIST_V2"
REFERENCE_BUDGET = 111419.0
RECOVERIES = (5, 10, 15)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_csv(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


@dataclass(frozen=True, order=True)
class PlanSignature:
    uniform_headway_min: int
    span_id: str
    span_start_min: int
    span_end_min: int
    span_minutes: int
    calendar_id: str
    annual_service_days: int
    extension_share: float

    def key_for(self, scenario_id: str) -> ServicePlanKey:
        return ServicePlanKey(
            scenario_id=scenario_id,
            uniform_headway_min=self.uniform_headway_min,
            span_id=self.span_id,
            calendar_id=self.calendar_id,
            extension_share=self.extension_share,
        )


def load_policy_groups(path: Path):
    groups: dict[PlanSignature, dict[int, int]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {
            "policy_index", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
            "span_minutes", "calendar_id", "annual_service_days", "recovery_min", "extension_share",
            "exact_timetable", "s8_phase_selected",
        }
        if not required <= set(r.fieldnames or []):
            raise ValueError("Policy grid schema mismatch")
        indices = set()
        for line_no, row in enumerate(r, 2):
            idx = int(row["policy_index"])
            if idx in indices:
                raise ValueError(f"Duplicate policy index {idx}")
            indices.add(idx)
            if row["exact_timetable"].lower() != "false" or row["s8_phase_selected"].lower() != "false":
                raise ValueError("Upstream policy grid contains a forbidden timetable/phase selection")
            sig = PlanSignature(
                uniform_headway_min=int(row["uniform_headway_min"]),
                span_id=row["span_id"],
                span_start_min=int(row["span_start_min"]),
                span_end_min=int(row["span_end_min"]),
                span_minutes=int(row["span_minutes"]),
                calendar_id=row["calendar_id"],
                annual_service_days=int(row["annual_service_days"]),
                extension_share=float(row["extension_share"]),
            )
            recovery = int(row["recovery_min"])
            if recovery in groups[sig]:
                raise ValueError(f"Duplicate recovery {recovery} for {sig}")
            groups[sig][recovery] = idx
    if len(indices) != 288 or len(groups) != 96:
        raise ValueError(f"Unexpected policy universe: {len(indices)} policies / {len(groups)} plan signatures")
    masks = {}
    for sig, recovery_map in groups.items():
        if set(recovery_map) != set(RECOVERIES):
            raise ValueError(f"Incomplete recovery sensitivity for {sig}")
        mask = 0
        for idx in recovery_map.values():
            mask |= 1 << idx
        masks[sig] = mask
    return dict(groups), masks


def load_structural_inputs(access_path: Path, territorial_path: Path):
    access: dict[str, dict[str, str]] = {}
    with open_csv(access_path) as f:
        r = csv.DictReader(f)
        required = {
            "scenario_id", "topology_family",
            "public_population_covered_10min", "public_population_coverage_share_10min",
            "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
            "public_plus_extensions_population_covered_10min", "public_plus_extensions_population_coverage_share_10min",
            "public_plus_extensions_worst_municipality_10min", "public_plus_extensions_worst_municipality_coverage_share_10min",
        }
        if not required <= set(r.fieldnames or []):
            raise ValueError("Access schema mismatch")
        for row in r:
            sid = row["scenario_id"]
            if sid in access:
                raise ValueError(f"Duplicate access scenario {sid}")
            access[sid] = {k: row[k] for k in required}

    territorial: dict[str, dict[str, str]] = {}
    with open_csv(territorial_path) as f:
        r = csv.DictReader(f)
        required = {
            "scenario_id", "topology_family",
            "public_structurally_addressable_od_relation_count",
            "public_structurally_addressable_worker_od_mass_upper_bound",
            "public_plus_extensions_structurally_addressable_od_relation_count",
            "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
        }
        if not required <= set(r.fieldnames or []):
            raise ValueError("Territorial schema mismatch")
        for row in r:
            sid = row["scenario_id"]
            if sid in territorial:
                raise ValueError(f"Duplicate territorial scenario {sid}")
            territorial[sid] = {k: row[k] for k in required}

    if len(access) != 100000 or set(access) != set(territorial):
        raise ValueError("Structural scenario universes do not reconcile to 100000 common scenarios")

    public_points: dict[str, MetricPoint] = {}
    extension_points: dict[str, MetricPoint] = {}
    families: dict[str, str] = {}
    for sid in access:
        a, t = access[sid], territorial[sid]
        if a["topology_family"] != t["topology_family"]:
            raise ValueError(f"Family mismatch for {sid}")
        families[sid] = a["topology_family"]
        public_points[sid] = MetricPoint.from_values(
            a["public_population_coverage_share_10min"],
            a["public_worst_municipality_coverage_share_10min"],
            t["public_structurally_addressable_worker_od_mass_upper_bound"],
        )
        extension_points[sid] = MetricPoint.from_values(
            a["public_plus_extensions_population_coverage_share_10min"],
            a["public_plus_extensions_worst_municipality_coverage_share_10min"],
            t["public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound"],
        )
    return access, territorial, families, public_points, extension_points


def validate_upstream(args):
    av, tv, sv, ov, fv = (
        loadj(args.access_validation), loadj(args.territorial_validation), loadj(args.service_validation),
        loadj(args.operational_validation), loadj(args.s8_validation),
    )
    if av.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or av.get("lineage", {}).get("scenario_output_sha256") != sha(args.access):
        raise ValueError("Access/Equity V2 is not certified")
    if tv.get("status") != "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD" or tv.get("lineage", {}).get("scenario_output_sha256") != sha(args.territorial):
        raise ValueError("Territorial V2 is not certified")
    if sv.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD" or sv.get("lineage", {}).get("feasibility_output_sha256") != sha(args.service_feasibility):
        raise ValueError("Service Policy Search V2 is not certified")
    if sv.get("lineage", {}).get("policy_grid_sha256") != sha(args.policy_grid):
        raise ValueError("Policy grid hash mismatch")
    if int(sv.get("feasible_scenario_counts_by_budget", {}).get("reference", -1)) != 69186:
        raise ValueError("Unexpected reference-feasible scenario count")
    caps = [float(v) for v in sv.get("budget_caps_annual_bus_km", [])]
    if len(caps) != 6 or not math.isclose(caps[2], REFERENCE_BUDGET, rel_tol=0, abs_tol=1e-9):
        raise ValueError("Unexpected reference budget")
    if ov.get("status") != "PASS_OPERATIONAL_SCREENING_V2_BUILD" or ov.get("lineage", {}).get("operational_screening_sha256") != sha(args.operational):
        raise ValueError("Operational Screening V2 is not certified")
    if fv.get("status") != "PASS_S8_SCENARIO_FEEDER_ENVELOPE_V2_BUILD" or fv.get("lineage", {}).get("output_sha256") != sha(args.s8_feeder):
        raise ValueError("S8 Scenario Feeder Envelope V2 is not certified")
    for field in ("route_weighting_applied", "worker_reference_assigned_to_routes", "cross_route_phase_selected", "joint_vehicle_block_timetable_feasibility_evaluated", "full_gjt_calculated", "topology_ranked", "service_policy_selected"):
        if fv.get(field) is not False:
            raise ValueError(f"S8 feeder envelope violates {field}=false")
    return av, tv, sv, ov, fv


def load_robust_reference_eligibility(path: Path, families, plan_masks):
    eligible_by_plan: dict[PlanSignature, list[str]] = {sig: [] for sig in plan_masks}
    robust_pair_count = 0
    scenario_with_any = 0
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {"scenario_id", "topology_family", "feasible_policy_mask_hex_reference"}
        if not required <= set(r.fieldnames or []):
            raise ValueError("Service feasibility schema mismatch")
        seen = set()
        for row in r:
            sid = row["scenario_id"]
            if sid not in families or sid in seen:
                raise ValueError(f"Unknown/duplicate service scenario {sid}")
            seen.add(sid)
            family = row["topology_family"]
            if family != families[sid]:
                raise ValueError(f"Service family mismatch for {sid}")
            feasible_mask = int(row["feasible_policy_mask_hex_reference"], 16)
            any_plan = False
            for sig, required_mask in plan_masks.items():
                if family != "scheduled_extensions" and not math.isclose(sig.extension_share, 0.0, abs_tol=1e-12):
                    continue
                if (feasible_mask & required_mask) == required_mask:
                    eligible_by_plan[sig].append(sid)
                    robust_pair_count += 1
                    any_plan = True
            if any_plan:
                scenario_with_any += 1
    if len(seen) != 100000:
        raise ValueError("Service feasibility does not cover 100000 scenarios")
    return eligible_by_plan, robust_pair_count, scenario_with_any


def build_structural_shortlist(eligible_by_plan, families, public_points, extension_points):
    shortlist: dict[tuple[str, PlanSignature], set[str]] = {}
    public_frontier_pair_count = 0
    extension_upper_pair_count = 0
    for sig, ids in eligible_by_plan.items():
        if not ids:
            continue
        public_frontier = nondominated_metric_points(public_points[sid] for sid in ids)
        extension_frontier = frozenset()
        if sig.extension_share > 0:
            scheduled_ids = [sid for sid in ids if families[sid] == "scheduled_extensions"]
            if scheduled_ids:
                extension_frontier = nondominated_metric_points(extension_points[sid] for sid in scheduled_ids)
        for sid in ids:
            basis = set()
            if public_points[sid] in public_frontier:
                basis.add("PUBLIC")
                public_frontier_pair_count += 1
            if sig.extension_share > 0 and families[sid] == "scheduled_extensions" and extension_points[sid] in extension_frontier:
                basis.add("EXTENSION_UPPER_BOUND")
                extension_upper_pair_count += 1
            if basis:
                shortlist[(sid, sig)] = basis
    return shortlist, public_frontier_pair_count, extension_upper_pair_count


def load_operational_subset(path: Path, wanted: set[str]):
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {
            "scenario_id", "topology_family", "public_route_count", "operational_screen_status",
            "public_equal_pattern_set_cycle_distance_km_lower_bound",
            "public_equal_pattern_set_cycle_runtime_min_lower_bound",
            "extension_equal_pattern_set_cycle_distance_km_lower_bound",
            "extension_equal_pattern_set_cycle_runtime_min_lower_bound",
            "public_explicit_proposed_stop_count", "public_explicit_existing_stop_count",
            "public_explicit_field_check_pending_count",
        }
        if not required <= set(r.fieldnames or []):
            raise ValueError("Operational screening schema mismatch")
        for row in r:
            sid = row["scenario_id"]
            if sid not in wanted:
                continue
            if row["operational_screen_status"] != "PASS_TO_SERVICE_POLICY_SEARCH":
                raise ValueError(f"Shortlisted scenario {sid} is not operational-pass")
            if sid in out:
                raise ValueError(f"Duplicate operational scenario {sid}")
            out[sid] = {k: row[k] for k in required}
    if set(out) != wanted:
        raise ValueError(f"Missing operational rows for {len(wanted - set(out))} shortlisted scenarios")
    return out


def plan_resources(sig: PlanSignature, op: dict[str, str]):
    public_d = float(op["public_equal_pattern_set_cycle_distance_km_lower_bound"])
    public_t = float(op["public_equal_pattern_set_cycle_runtime_min_lower_bound"])
    ext_d_raw = op["extension_equal_pattern_set_cycle_distance_km_lower_bound"].strip()
    ext_t_raw = op["extension_equal_pattern_set_cycle_runtime_min_lower_bound"].strip()
    if sig.extension_share > 0:
        if not ext_d_raw or not ext_t_raw:
            raise ValueError("Positive extension share without extension operational cycle")
        ext_d, ext_t = float(ext_d_raw), float(ext_t_raw)
        expected_d = (1.0 - sig.extension_share) * public_d + sig.extension_share * ext_d
        expected_t = (1.0 - sig.extension_share) * public_t + sig.extension_share * ext_t
    else:
        expected_d, expected_t = public_d, public_t
    annual_km = expected_d * (sig.span_minutes / sig.uniform_headway_min) * sig.annual_service_days
    route_count = int(op["public_route_count"])
    fleets = {r: math.ceil((expected_t + r * route_count) / sig.uniform_headway_min) for r in RECOVERIES}
    if annual_km > REFERENCE_BUDGET + 1e-6:
        raise ValueError(f"Robust-feasible shortlist plan exceeds reference budget: {annual_km}")
    return expected_d, expected_t, annual_km, fleets


S8_FIELDS = [
    "public_route_count", "public_complete_match_route_count", "public_complete_match_route_share",
    "public_all_routes_have_some_complete_match_phase", "public_any_route_has_some_complete_match_phase",
    "public_roundtrip_route_count", "public_roundtrip_complete_match_route_share",
    "public_roundtrip_best_complete_gap_min_min", "public_roundtrip_best_complete_gap_min_max",
    "public_roundtrip_worst_complete_gap_min_min", "public_roundtrip_worst_complete_gap_min_max",
    "public_rail_to_bus_only_route_count", "public_rail_to_bus_only_complete_match_route_share",
    "extension_route_count", "extension_complete_match_route_share",
    "extension_all_routes_have_some_complete_match_phase", "extension_any_route_has_some_complete_match_phase",
]


def load_s8_subset(path: Path, keys: set[tuple[str, int, str]]):
    out = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {"scenario_id", "topology_family", "uniform_headway_min", "span_id", *S8_FIELDS}
        if not required <= set(r.fieldnames or []):
            raise ValueError(f"S8 feeder schema missing: {sorted(required - set(r.fieldnames or []))}")
        for row in r:
            key = (row["scenario_id"], int(row["uniform_headway_min"]), row["span_id"])
            if key not in keys:
                continue
            if key in out:
                raise ValueError(f"Duplicate S8 shortlist key {key}")
            out[key] = {k: row[k] for k in S8_FIELDS | {"topology_family"}}
    if set(out) != keys:
        raise ValueError(f"Missing S8 timing rows for {len(keys - set(out))} shortlist keys")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--access", type=Path, required=True)
    p.add_argument("--access-validation", type=Path, required=True)
    p.add_argument("--territorial", type=Path, required=True)
    p.add_argument("--territorial-validation", type=Path, required=True)
    p.add_argument("--service-feasibility", type=Path, required=True)
    p.add_argument("--service-validation", type=Path, required=True)
    p.add_argument("--policy-grid", type=Path, required=True)
    p.add_argument("--operational", type=Path, required=True)
    p.add_argument("--operational-validation", type=Path, required=True)
    p.add_argument("--s8-feeder", type=Path, required=True)
    p.add_argument("--s8-validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    validate_upstream(args)
    groups, plan_masks = load_policy_groups(args.policy_grid)
    access, territorial, families, public_points, extension_points = load_structural_inputs(args.access, args.territorial)
    eligible_by_plan, robust_pair_count, robust_scenario_count = load_robust_reference_eligibility(
        args.service_feasibility, families, plan_masks
    )
    shortlist, public_pair_count, extension_pair_count = build_structural_shortlist(
        eligible_by_plan, families, public_points, extension_points
    )
    if not shortlist:
        raise ValueError("Reference service-plan shortlist is empty")

    wanted_scenarios = {sid for sid, _ in shortlist}
    operational = load_operational_subset(args.operational, wanted_scenarios)
    s8_keys = {(sid, sig.uniform_headway_min, sig.span_id) for sid, sig in shortlist}
    s8 = load_s8_subset(args.s8_feeder, s8_keys)

    fields = [
        "plan_id", "scenario_id", "topology_family", "frontier_basis",
        "uniform_headway_min", "span_id", "span_start_min", "span_end_min", "span_minutes",
        "calendar_id", "annual_service_days", "extension_share",
        "public_population_covered_10min", "public_population_coverage_share_10min",
        "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
        "public_structurally_addressable_od_relation_count", "public_structurally_addressable_worker_od_mass_upper_bound",
        "public_plus_extensions_population_covered_10min", "public_plus_extensions_population_coverage_share_10min",
        "public_plus_extensions_worst_municipality_10min", "public_plus_extensions_worst_municipality_coverage_share_10min",
        "public_plus_extensions_structurally_addressable_od_relation_count", "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
        "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min", "annual_bus_km",
        "fleet_lower_bound_recovery5", "fleet_lower_bound_recovery10", "fleet_lower_bound_recovery15",
        "public_explicit_proposed_stop_count", "public_explicit_existing_stop_count", "public_explicit_field_check_pending_count",
        *[f"s8_{name}" for name in S8_FIELDS],
        "reference_budget_robust_all_recoveries", "structural_shortlist", "frequent_service_30min_or_better",
        "extension_access_realised", "weighted_composite_score_used", "worker_reference_assigned_to_routes",
        "s8_phase_selected", "joint_vehicle_block_timetable_feasibility_evaluated", "exact_timetable_constructed",
        "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
    ]

    rows = []
    plan_ids = set()
    for sid, sig in sorted(shortlist, key=lambda x: (x[0], x[1])):
        a, t, op = access[sid], territorial[sid], operational[sid]
        if op["topology_family"] != families[sid]:
            raise ValueError(f"Operational family mismatch for {sid}")
        expected_d, expected_t, annual_km, fleets = plan_resources(sig, op)
        s8row = s8[(sid, sig.uniform_headway_min, sig.span_id)]
        if s8row["topology_family"] != families[sid]:
            raise ValueError(f"S8 family mismatch for {sid}")
        plan_id = sig.key_for(sid).plan_id
        if plan_id in plan_ids:
            raise ValueError(f"Duplicate plan ID {plan_id}")
        plan_ids.add(plan_id)
        row = {
            "plan_id": plan_id,
            "scenario_id": sid,
            "topology_family": families[sid],
            "frontier_basis": "+".join(sorted(shortlist[(sid, sig)])),
            "uniform_headway_min": sig.uniform_headway_min,
            "span_id": sig.span_id,
            "span_start_min": sig.span_start_min,
            "span_end_min": sig.span_end_min,
            "span_minutes": sig.span_minutes,
            "calendar_id": sig.calendar_id,
            "annual_service_days": sig.annual_service_days,
            "extension_share": f"{sig.extension_share:.2f}",
            "public_population_covered_10min": a["public_population_covered_10min"],
            "public_population_coverage_share_10min": a["public_population_coverage_share_10min"],
            "public_worst_municipality_10min": a["public_worst_municipality_10min"],
            "public_worst_municipality_coverage_share_10min": a["public_worst_municipality_coverage_share_10min"],
            "public_structurally_addressable_od_relation_count": t["public_structurally_addressable_od_relation_count"],
            "public_structurally_addressable_worker_od_mass_upper_bound": t["public_structurally_addressable_worker_od_mass_upper_bound"],
            "public_plus_extensions_population_covered_10min": a["public_plus_extensions_population_covered_10min"],
            "public_plus_extensions_population_coverage_share_10min": a["public_plus_extensions_population_coverage_share_10min"],
            "public_plus_extensions_worst_municipality_10min": a["public_plus_extensions_worst_municipality_10min"],
            "public_plus_extensions_worst_municipality_coverage_share_10min": a["public_plus_extensions_worst_municipality_coverage_share_10min"],
            "public_plus_extensions_structurally_addressable_od_relation_count": t["public_plus_extensions_structurally_addressable_od_relation_count"],
            "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound": t["public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound"],
            "expected_pattern_set_cycle_distance_km": f"{expected_d:.9f}",
            "expected_pattern_set_cycle_runtime_min": f"{expected_t:.9f}",
            "annual_bus_km": f"{annual_km:.6f}",
            "fleet_lower_bound_recovery5": fleets[5],
            "fleet_lower_bound_recovery10": fleets[10],
            "fleet_lower_bound_recovery15": fleets[15],
            "public_explicit_proposed_stop_count": op["public_explicit_proposed_stop_count"],
            "public_explicit_existing_stop_count": op["public_explicit_existing_stop_count"],
            "public_explicit_field_check_pending_count": op["public_explicit_field_check_pending_count"],
            **{f"s8_{name}": s8row[name] for name in S8_FIELDS},
            "reference_budget_robust_all_recoveries": "true",
            "structural_shortlist": "true",
            "frequent_service_30min_or_better": "true" if sig.uniform_headway_min <= 30 else "false",
            "extension_access_realised": "false",
            "weighted_composite_score_used": "false",
            "worker_reference_assigned_to_routes": "false",
            "s8_phase_selected": "false",
            "joint_vehicle_block_timetable_feasibility_evaluated": "false",
            "exact_timetable_constructed": "false",
            "topology_ranked": "false",
            "service_policy_selected": "false",
            "primary_selected": "false",
            "runner_up_selected": "false",
        }
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    headway_counts = Counter(int(r["uniform_headway_min"]) for r in rows)
    family_counts = Counter(r["topology_family"] for r in rows)
    frequent_rows = [r for r in rows if r["frequent_service_30min_or_better"] == "true"]
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "reference_budget_bus_km_year": REFERENCE_BUDGET,
        "scenario_count_upstream": 100000,
        "reference_feasible_scenario_count_upstream": 69186,
        "passenger_facing_plan_signature_count": len(groups),
        "recovery_sensitivities_min": list(RECOVERIES),
        "robust_reference_feasible_scenario_plan_pair_count": robust_pair_count,
        "robust_reference_feasible_scenario_count": robust_scenario_count,
        "shortlist_scenario_plan_count": len(rows),
        "shortlist_unique_scenario_count": len(wanted_scenarios),
        "shortlist_public_frontier_memberships": public_pair_count,
        "shortlist_extension_upper_bound_frontier_memberships": extension_pair_count,
        "shortlist_headway_counts": dict(sorted(headway_counts.items())),
        "shortlist_family_counts": dict(sorted(family_counts.items())),
        "frequent_30min_or_better_shortlist_count": len(frequent_rows),
        "frequent_30min_or_better_unique_scenario_count": len({r["scenario_id"] for r in frequent_rows}),
        "s8_timing_key_count": len(s8_keys),
        "recovery_semantics": "ROBUSTNESS_SENSITIVITY_COLLAPSED_INTO_ONE_PASSENGER_FACING_PLAN; ALL_5_10_15_VARIANTS_REFERENCE_BUDGET_FEASIBLE",
        "scheduled_extension_semantics": "UNION_OF_PUBLIC_FRONTIER_AND_ALL_EXTENSION_ANCHORS_UPPER_BOUND_FRONTIER; EXTENSION_ACCESS_NOT_REALISED_UNTIL_EXPLICIT_TIMETABLE",
        "s8_semantics": "ROUTE_UNWEIGHTED_TIMING_ENVELOPE_AT_MATCHING_HEADWAY_AND_SPAN; NO_WORKER_ROUTE_WEIGHTS; NO_COMMON_PHASE_SELECTED",
        "weighted_composite_score_used": False,
        "worker_reference_assigned_to_routes": False,
        "full_passenger_gjt_calculated": False,
        "s8_phase_selected": False,
        "joint_vehicle_block_timetable_feasibility_evaluated": False,
        "exact_timetable_constructed": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "access_sha256": sha(args.access),
            "access_validation_sha256": sha(args.access_validation),
            "territorial_sha256": sha(args.territorial),
            "territorial_validation_sha256": sha(args.territorial_validation),
            "service_feasibility_sha256": sha(args.service_feasibility),
            "service_validation_sha256": sha(args.service_validation),
            "policy_grid_sha256": sha(args.policy_grid),
            "operational_sha256": sha(args.operational),
            "operational_validation_sha256": sha(args.operational_validation),
            "s8_feeder_sha256": sha(args.s8_feeder),
            "s8_validation_sha256": sha(args.s8_validation),
            "output_sha256": sha(args.output),
        },
    }
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
