#!/usr/bin/env python3
"""Build the reference-budget Phase 2 service-plan shortlist V2.

Start from all reference-feasible scenarios. For each identical passenger-facing
policy (headway, span, calendar, extension share), retain structural Pareto
scenarios. Recovery 5/10/15 remains a robustness sensitivity of one plan, so all
three variants must fit the 111,419 bus-km/year reference envelope.

Scheduled extensions are protected from premature pruning by taking the union
of a base-public frontier and an all-extension-anchors *upper-bound* frontier.
The output then attaches joint plan resource calculations and the certified
route-unweighted S8 envelope for the same headway/span. No common S8 phase,
exact timetable, topology ranking, PRIMARY or RUNNER-UP is selected here.
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
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_csv(path: Path):
    return gzip.open(path, "rt", encoding="utf-8-sig", newline="") if path.suffix == ".gz" else path.open("r", encoding="utf-8-sig", newline="")


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

    def plan_id(self, scenario_id: str) -> str:
        return ServicePlanKey(
            scenario_id=scenario_id,
            uniform_headway_min=self.uniform_headway_min,
            span_id=self.span_id,
            calendar_id=self.calendar_id,
            extension_share=self.extension_share,
        ).plan_id


def load_policy_groups(path: Path):
    groups: dict[PlanSignature, dict[int, int]] = defaultdict(dict)
    indices = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "policy_index", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
            "span_minutes", "calendar_id", "annual_service_days", "recovery_min", "extension_share",
            "exact_timetable", "s8_phase_selected",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Policy grid schema mismatch")
        for row in reader:
            idx = int(row["policy_index"])
            if idx in indices:
                raise ValueError(f"Duplicate policy index {idx}")
            indices.add(idx)
            if row["exact_timetable"].lower() != "false" or row["s8_phase_selected"].lower() != "false":
                raise ValueError("Policy grid already contains forbidden timetable/phase selection")
            sig = PlanSignature(
                int(row["uniform_headway_min"]), row["span_id"], int(row["span_start_min"]),
                int(row["span_end_min"]), int(row["span_minutes"]), row["calendar_id"],
                int(row["annual_service_days"]), float(row["extension_share"]),
            )
            recovery = int(row["recovery_min"])
            if recovery in groups[sig]:
                raise ValueError(f"Duplicate recovery {recovery} for {sig}")
            groups[sig][recovery] = idx
    if len(indices) != 288 or len(groups) != 96:
        raise ValueError(f"Unexpected policy universe {len(indices)} / {len(groups)}")
    masks = {}
    for sig, recovery_map in groups.items():
        if set(recovery_map) != set(RECOVERIES):
            raise ValueError(f"Incomplete recovery sensitivity for {sig}")
        masks[sig] = sum(1 << idx for idx in recovery_map.values())
    return dict(groups), masks


def load_structural(access_path: Path, territorial_path: Path):
    access_fields = {
        "scenario_id", "topology_family", "public_population_covered_10min",
        "public_population_coverage_share_10min", "public_worst_municipality_10min",
        "public_worst_municipality_coverage_share_10min", "public_plus_extensions_population_covered_10min",
        "public_plus_extensions_population_coverage_share_10min", "public_plus_extensions_worst_municipality_10min",
        "public_plus_extensions_worst_municipality_coverage_share_10min",
    }
    territorial_fields = {
        "scenario_id", "topology_family", "public_structurally_addressable_od_relation_count",
        "public_structurally_addressable_worker_od_mass_upper_bound",
        "public_plus_extensions_structurally_addressable_od_relation_count",
        "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
    }

    def compact(path: Path, required: set[str], label: str):
        rows = {}
        with open_csv(path) as handle:
            reader = csv.DictReader(handle)
            if not required <= set(reader.fieldnames or []):
                raise ValueError(f"{label} schema mismatch")
            for row in reader:
                sid = row["scenario_id"]
                if sid in rows:
                    raise ValueError(f"Duplicate {label} scenario {sid}")
                rows[sid] = {key: row[key] for key in required}
        return rows

    access = compact(access_path, access_fields, "access")
    territorial = compact(territorial_path, territorial_fields, "territorial")
    if len(access) != 100000 or set(access) != set(territorial):
        raise ValueError("Structural universes do not reconcile to 100000 common scenarios")

    families, public_points, extension_points = {}, {}, {}
    for sid, a in access.items():
        t = territorial[sid]
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
    av = loadj(args.access_validation)
    tv = loadj(args.territorial_validation)
    sv = loadj(args.service_validation)
    ov = loadj(args.operational_validation)
    fv = loadj(args.s8_validation)
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
        raise ValueError("S8 feeder envelope V2 is not certified")
    for field in (
        "route_weighting_applied", "worker_reference_assigned_to_routes", "cross_route_phase_selected",
        "joint_vehicle_block_timetable_feasibility_evaluated", "full_gjt_calculated",
        "topology_ranked", "service_policy_selected",
    ):
        if fv.get(field) is not False:
            raise ValueError(f"S8 envelope violates {field}=false")


def robust_reference_eligibility(path: Path, families, plan_masks):
    eligible = {sig: [] for sig in plan_masks}
    robust_pairs = robust_scenarios = 0
    seen = set()
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scenario_id", "topology_family", "feasible_policy_mask_hex_reference"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Service feasibility schema mismatch")
        for row in reader:
            sid, family = row["scenario_id"], row["topology_family"]
            if sid not in families or sid in seen or families[sid] != family:
                raise ValueError(f"Service scenario mismatch/duplicate {sid}")
            seen.add(sid)
            mask = int(row["feasible_policy_mask_hex_reference"], 16)
            any_plan = False
            for sig, required_mask in plan_masks.items():
                if family != "scheduled_extensions" and not math.isclose(sig.extension_share, 0.0, abs_tol=1e-12):
                    continue
                if (mask & required_mask) == required_mask:
                    eligible[sig].append(sid)
                    robust_pairs += 1
                    any_plan = True
            robust_scenarios += int(any_plan)
    if len(seen) != 100000:
        raise ValueError("Service feasibility does not cover 100000 scenarios")
    return eligible, robust_pairs, robust_scenarios


def structural_shortlist(eligible, families, public_points, extension_points):
    shortlist = {}
    public_memberships = extension_memberships = 0
    for sig, ids in eligible.items():
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
                public_memberships += 1
            if sig.extension_share > 0 and families[sid] == "scheduled_extensions" and extension_points[sid] in extension_frontier:
                basis.add("EXTENSION_UPPER_BOUND")
                extension_memberships += 1
            if basis:
                shortlist[(sid, sig)] = basis
    return shortlist, public_memberships, extension_memberships


def load_operational(path: Path, wanted: set[str]):
    required = {
        "scenario_id", "topology_family", "public_route_count", "operational_screen_status",
        "public_equal_pattern_set_cycle_distance_km_lower_bound", "public_equal_pattern_set_cycle_runtime_min_lower_bound",
        "extension_equal_pattern_set_cycle_distance_km_lower_bound", "extension_equal_pattern_set_cycle_runtime_min_lower_bound",
        "public_explicit_proposed_stop_count", "public_explicit_existing_stop_count", "public_explicit_field_check_pending_count",
    }
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Operational schema mismatch")
        for row in reader:
            sid = row["scenario_id"]
            if sid not in wanted:
                continue
            if sid in out or row["operational_screen_status"] != "PASS_TO_SERVICE_POLICY_SEARCH":
                raise ValueError(f"Invalid shortlisted operational row {sid}")
            out[sid] = {key: row[key] for key in required}
    if set(out) != wanted:
        raise ValueError(f"Missing {len(wanted-set(out))} shortlisted operational rows")
    return out


def resources(sig: PlanSignature, op: dict[str, str]):
    public_d = float(op["public_equal_pattern_set_cycle_distance_km_lower_bound"])
    public_t = float(op["public_equal_pattern_set_cycle_runtime_min_lower_bound"])
    if sig.extension_share > 0:
        ext_d_raw = op["extension_equal_pattern_set_cycle_distance_km_lower_bound"].strip()
        ext_t_raw = op["extension_equal_pattern_set_cycle_runtime_min_lower_bound"].strip()
        if not ext_d_raw or not ext_t_raw:
            raise ValueError("Positive extension share without extension operational cycle")
        expected_d = (1-sig.extension_share)*public_d + sig.extension_share*float(ext_d_raw)
        expected_t = (1-sig.extension_share)*public_t + sig.extension_share*float(ext_t_raw)
    else:
        expected_d, expected_t = public_d, public_t
    annual_km = expected_d * (sig.span_minutes / sig.uniform_headway_min) * sig.annual_service_days
    route_count = int(op["public_route_count"])
    fleets = {r: math.ceil((expected_t + r*route_count) / sig.uniform_headway_min) for r in RECOVERIES}
    if annual_km > REFERENCE_BUDGET + 1e-6:
        raise ValueError(f"Shortlisted robust plan exceeds reference budget: {annual_km}")
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


def load_s8(path: Path, wanted: set[tuple[str, int, str]]):
    required = {"scenario_id", "topology_family", "uniform_headway_min", "span_id", *S8_FIELDS}
    keep_fields = set(S8_FIELDS) | {"topology_family"}
    out = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"S8 feeder schema missing {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            key = (row["scenario_id"], int(row["uniform_headway_min"]), row["span_id"])
            if key not in wanted:
                continue
            if key in out:
                raise ValueError(f"Duplicate S8 key {key}")
            out[key] = {field: row[field] for field in keep_fields}
    if set(out) != wanted:
        raise ValueError(f"Missing {len(wanted-set(out))} S8 shortlist timing rows")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "access", "access_validation", "territorial", "territorial_validation",
        "service_feasibility", "service_validation", "policy_grid", "operational",
        "operational_validation", "s8_feeder", "s8_validation", "output", "validation",
    ):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = parser.parse_args()

    validate_upstream(args)
    groups, plan_masks = load_policy_groups(args.policy_grid)
    access, territorial, families, public_points, extension_points = load_structural(args.access, args.territorial)
    eligible, robust_pair_count, robust_scenario_count = robust_reference_eligibility(args.service_feasibility, families, plan_masks)
    shortlist, public_memberships, extension_memberships = structural_shortlist(eligible, families, public_points, extension_points)
    if not shortlist:
        raise ValueError("Reference service-plan shortlist is empty")

    scenario_ids = {sid for sid, _ in shortlist}
    operational = load_operational(args.operational, scenario_ids)
    s8_keys = {(sid, sig.uniform_headway_min, sig.span_id) for sid, sig in shortlist}
    s8 = load_s8(args.s8_feeder, s8_keys)

    base_fields = [
        "plan_id", "scenario_id", "topology_family", "frontier_basis", "uniform_headway_min",
        "span_id", "span_start_min", "span_end_min", "span_minutes", "calendar_id",
        "annual_service_days", "extension_share", "public_population_covered_10min",
        "public_population_coverage_share_10min", "public_worst_municipality_10min",
        "public_worst_municipality_coverage_share_10min", "public_structurally_addressable_od_relation_count",
        "public_structurally_addressable_worker_od_mass_upper_bound", "public_plus_extensions_population_covered_10min",
        "public_plus_extensions_population_coverage_share_10min", "public_plus_extensions_worst_municipality_10min",
        "public_plus_extensions_worst_municipality_coverage_share_10min",
        "public_plus_extensions_structurally_addressable_od_relation_count",
        "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
        "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min", "annual_bus_km",
        "fleet_lower_bound_recovery5", "fleet_lower_bound_recovery10", "fleet_lower_bound_recovery15",
        "public_explicit_proposed_stop_count", "public_explicit_existing_stop_count", "public_explicit_field_check_pending_count",
    ]
    flag_fields = [
        "reference_budget_robust_all_recoveries", "structural_shortlist", "frequent_service_30min_or_better",
        "extension_access_realised", "weighted_composite_score_used", "worker_reference_assigned_to_routes",
        "s8_phase_selected", "joint_vehicle_block_timetable_feasibility_evaluated", "exact_timetable_constructed",
        "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
    ]
    fields = base_fields + [f"s8_{name}" for name in S8_FIELDS] + flag_fields

    rows, plan_ids = [], set()
    for sid, sig in sorted(shortlist, key=lambda item: (item[0], item[1])):
        a, t, op = access[sid], territorial[sid], operational[sid]
        if op["topology_family"] != families[sid]:
            raise ValueError(f"Operational family mismatch for {sid}")
        expected_d, expected_t, annual_km, fleets = resources(sig, op)
        s8row = s8[(sid, sig.uniform_headway_min, sig.span_id)]
        if s8row["topology_family"] != families[sid]:
            raise ValueError(f"S8 family mismatch for {sid}")
        plan_id = sig.plan_id(sid)
        if plan_id in plan_ids:
            raise ValueError(f"Duplicate plan ID {plan_id}")
        plan_ids.add(plan_id)
        row = {
            "plan_id": plan_id, "scenario_id": sid, "topology_family": families[sid],
            "frontier_basis": "+".join(sorted(shortlist[(sid, sig)])),
            "uniform_headway_min": sig.uniform_headway_min, "span_id": sig.span_id,
            "span_start_min": sig.span_start_min, "span_end_min": sig.span_end_min,
            "span_minutes": sig.span_minutes, "calendar_id": sig.calendar_id,
            "annual_service_days": sig.annual_service_days, "extension_share": f"{sig.extension_share:.2f}",
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
            "fleet_lower_bound_recovery5": fleets[5], "fleet_lower_bound_recovery10": fleets[10],
            "fleet_lower_bound_recovery15": fleets[15],
            "public_explicit_proposed_stop_count": op["public_explicit_proposed_stop_count"],
            "public_explicit_existing_stop_count": op["public_explicit_existing_stop_count"],
            "public_explicit_field_check_pending_count": op["public_explicit_field_check_pending_count"],
            **{f"s8_{name}": s8row[name] for name in S8_FIELDS},
            "reference_budget_robust_all_recoveries": "true", "structural_shortlist": "true",
            "frequent_service_30min_or_better": "true" if sig.uniform_headway_min <= 30 else "false",
            "extension_access_realised": "false", "weighted_composite_score_used": "false",
            "worker_reference_assigned_to_routes": "false", "s8_phase_selected": "false",
            "joint_vehicle_block_timetable_feasibility_evaluated": "false", "exact_timetable_constructed": "false",
            "topology_ranked": "false", "service_policy_selected": "false", "primary_selected": "false", "runner_up_selected": "false",
        }
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    frequent = [row for row in rows if row["frequent_service_30min_or_better"] == "true"]
    validation = {
        "status": STATUS, "contract": CONTRACT, "reference_budget_bus_km_year": REFERENCE_BUDGET,
        "scenario_count_upstream": 100000, "reference_feasible_scenario_count_upstream": 69186,
        "passenger_facing_plan_signature_count": len(groups), "recovery_sensitivities_min": list(RECOVERIES),
        "robust_reference_feasible_scenario_plan_pair_count": robust_pair_count,
        "robust_reference_feasible_scenario_count": robust_scenario_count,
        "shortlist_scenario_plan_count": len(rows), "shortlist_unique_scenario_count": len(scenario_ids),
        "shortlist_public_frontier_memberships": public_memberships,
        "shortlist_extension_upper_bound_frontier_memberships": extension_memberships,
        "shortlist_headway_counts": dict(sorted(Counter(int(row["uniform_headway_min"]) for row in rows).items())),
        "shortlist_family_counts": dict(sorted(Counter(row["topology_family"] for row in rows).items())),
        "frequent_30min_or_better_shortlist_count": len(frequent),
        "frequent_30min_or_better_unique_scenario_count": len({row["scenario_id"] for row in frequent}),
        "s8_timing_key_count": len(s8_keys),
        "recovery_semantics": "ROBUSTNESS_SENSITIVITY_COLLAPSED_INTO_ONE_PASSENGER_FACING_PLAN; ALL_5_10_15_VARIANTS_REFERENCE_BUDGET_FEASIBLE",
        "scheduled_extension_semantics": "UNION_OF_PUBLIC_FRONTIER_AND_ALL_EXTENSION_ANCHORS_UPPER_BOUND_FRONTIER; EXTENSION_ACCESS_NOT_REALISED_UNTIL_EXPLICIT_TIMETABLE",
        "s8_semantics": "ROUTE_UNWEIGHTED_TIMING_ENVELOPE_AT_MATCHING_HEADWAY_AND_SPAN; NO_WORKER_ROUTE_WEIGHTS; NO_COMMON_PHASE_SELECTED",
        "weighted_composite_score_used": False, "worker_reference_assigned_to_routes": False,
        "full_passenger_gjt_calculated": False, "s8_phase_selected": False,
        "joint_vehicle_block_timetable_feasibility_evaluated": False, "exact_timetable_constructed": False,
        "topology_ranked": False, "service_policy_selected": False, "primary_selected": False, "runner_up_selected": False,
        "lineage": {
            "access_sha256": sha(args.access), "access_validation_sha256": sha(args.access_validation),
            "territorial_sha256": sha(args.territorial), "territorial_validation_sha256": sha(args.territorial_validation),
            "service_feasibility_sha256": sha(args.service_feasibility), "service_validation_sha256": sha(args.service_validation),
            "policy_grid_sha256": sha(args.policy_grid), "operational_sha256": sha(args.operational),
            "operational_validation_sha256": sha(args.operational_validation), "s8_feeder_sha256": sha(args.s8_feeder),
            "s8_validation_sha256": sha(args.s8_validation), "output_sha256": sha(args.output),
        },
    }
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
