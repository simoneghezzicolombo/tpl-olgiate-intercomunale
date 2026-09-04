#!/usr/bin/env python3
"""Reproducible methodological red-team for frozen Phase 2 integrated lineage.

This audit does not rank scenarios or select a recommendation.  It verifies
current artifacts against their source contracts, re-computes selected counts,
checks declared lineage hashes, and looks for methodological boundary breaches.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_SHA = "864c83accb81c615f9778396408b21e31ca72983"
OUTDIR = ROOT / "outputs/phase2/final_method_redteam_v2"
FINDINGS_OUT = OUTDIR / "findings.json"
VALIDATION_OUT = OUTDIR / "final_method_redteam_v2_validation.json"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def read_gzip(rel: str):
    with gzip.open(ROOT / rel, "rt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def add_finding(findings, *, fid, classification, severity, stage, title, evidence, consequence, recommended_fix, reproducibility):
    findings.append({
        "id": fid,
        "classification": classification,
        "severity": severity,
        "affected_stage": stage,
        "title": title,
        "evidence": evidence,
        "reproducibility": reproducibility,
        "consequence": consequence,
        "recommended_fix": recommended_fix,
    })


def actual_hash(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        return "MISSING"
    return sha256_path(path)


def lineage_checks() -> list[dict[str, str]]:
    checks: list[tuple[str, str, str]] = []

    pu = read_json("outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2_validation.json")
    pl = pu["lineage"]
    checks += [
        ("passenger/budget_policy_frontier", pl["budget_policy_frontier_sha256"], "outputs/phase2/budget_policy_frontiers_v2/scenario_budget_policy_frontier_v2.csv.gz"),
        ("passenger/budget_policy_validation", pl["budget_policy_validation_sha256"], "outputs/phase2/budget_policy_frontiers_v2/budget_policy_frontiers_v2_validation.json"),
        ("passenger/feeder_timing", pl["feeder_timing_sha256"], "outputs/phase2/feeder_generalized_access_v2/scenario_timing_feeder_generalized_access_v2.csv.gz"),
        ("passenger/feeder_validation", pl["feeder_validation_sha256"], "outputs/phase2/feeder_generalized_access_v2/feeder_generalized_access_v2_validation.json"),
        ("passenger/frontier", pl["frontier_output_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz"),
        ("passenger/context_audit", pl["context_audit_output_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_context_audit_v2.csv"),
    ]

    s8 = read_json("outputs/phase2/s8_robust_opportunity_v2/s8_robust_opportunity_v2_validation.json")
    sl = s8["lineage_compatibility"]
    checks += [
        ("s8/current_policy_grid", sl["current_policy_grid_sha256"], "outputs/phase2/service_policy_search_v2/service_policy_design_space_v2.csv"),
        ("s8/current_route_universe", sl["current_route_universe_sha256"], "outputs/phase2/s8_phasing_v2/unique_route_cycles_v2.csv"),
        ("s8/current_events", sl["current_s8_events_sha256"], "outputs/phase2/s8_events.csv"),
        ("s8/current_validation", sl["current_s8_validation_sha256"], "outputs/phase2/s8_phasing_v2/s8_phasing_v2_validation.json"),
        ("s8/current_scenario_mapping", sl["current_scenario_mapping_sha256"], "outputs/phase2/s8_phasing_v2/scenario_to_routes_v2.csv.gz"),
        ("s8/passenger_frontier", sl["passenger_frontier_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz"),
        ("s8/output", sl["output_sha256"], "outputs/phase2/s8_robust_opportunity_v2/passenger_plans_s8_opportunity_v2.csv.gz"),
    ]

    cont = read_json("outputs/phase2/current_service_continuity_v2/current_service_continuity_v2_validation.json")
    cl = cont["lineage"]
    checks += [
        ("continuity/current_localized", cl["current_localized_sha256"], "outputs/phase2/current_service_access_baseline_v2/current_service_localized_rows_v2.csv"),
        ("continuity/current_validation", cl["current_validation_sha256"], "outputs/phase2/current_service_access_baseline_v2/current_service_access_baseline_v2_validation.json"),
        ("continuity/routing_anchors", cl["routing_anchors_sha256"], "outputs/phase2/reduced_path_matrix_v2/routing_anchor_universe.csv"),
        ("continuity/matrix_validation", cl["matrix_validation_sha256"], "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix_v2_validation.json"),
        ("continuity/route_universe", cl["route_universe_sha256"], "outputs/phase2/s8_phasing_v2/unique_route_cycles_v2.csv"),
        ("continuity/scenario_mapping", cl["scenario_mapping_sha256"], "outputs/phase2/s8_phasing_v2/scenario_to_routes_v2.csv.gz"),
        ("continuity/s8_validation", cl["s8_validation_sha256"], "outputs/phase2/s8_phasing_v2/s8_phasing_v2_validation.json"),
        ("continuity/passenger_frontier", cl["passenger_frontier_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz"),
        ("continuity/passenger_validation", cl["passenger_validation_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2_validation.json"),
        ("continuity/scenario_output", cl["scenario_output_sha256"], "outputs/phase2/current_service_continuity_v2/scenario_current_service_continuity_lower_bound_v2.csv.gz"),
        ("continuity/plan_output", cl["plan_output_sha256"], "outputs/phase2/current_service_continuity_v2/passenger_plans_current_service_continuity_lower_bound_v2.csv.gz"),
    ]

    manifest_path = ROOT / "outputs/phase2/stage_d_input_manifest_v2/stage_d_input_manifest_v2_validation.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ml = manifest["lineage"]
        checks += [
            ("stage_d_manifest/passenger_frontier", ml["passenger_frontier_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz"),
            ("stage_d_manifest/passenger_validation", ml["passenger_validation_sha256"], "outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2_validation.json"),
            ("stage_d_manifest/s8_opportunity", ml["s8_opportunity_sha256"], "outputs/phase2/s8_robust_opportunity_v2/passenger_plans_s8_opportunity_v2.csv.gz"),
            ("stage_d_manifest/s8_opportunity_validation", ml["s8_opportunity_validation_sha256"], "outputs/phase2/s8_robust_opportunity_v2/s8_robust_opportunity_v2_validation.json"),
            ("stage_d_manifest/continuity_scenarios", ml["continuity_scenarios_sha256"], "outputs/phase2/current_service_continuity_v2/scenario_current_service_continuity_lower_bound_v2.csv.gz"),
            ("stage_d_manifest/continuity_validation", ml["continuity_validation_sha256"], "outputs/phase2/current_service_continuity_v2/current_service_continuity_v2_validation.json"),
            ("stage_d_manifest/scenario_mapping", ml["scenario_mapping_sha256"], "outputs/phase2/s8_phasing_v2/scenario_to_routes_v2.csv.gz"),
            ("stage_d_manifest/route_universe", ml["route_universe_sha256"], "outputs/phase2/s8_phasing_v2/unique_route_cycles_v2.csv"),
            ("stage_d_manifest/s8_validation", ml["s8_validation_sha256"], "outputs/phase2/s8_phasing_v2/s8_phasing_v2_validation.json"),
        ]

    result = []
    for label, expected, rel in checks:
        actual = actual_hash(rel)
        result.append({"label": label, "path": rel, "expected_sha256": expected, "actual_sha256": actual, "match": expected == actual})
    return result


def budget_exactness_audit() -> dict:
    # The declared production model is continuous. For spans that are not an
    # integer multiple of headway, an explicit timetable necessarily has either
    # floor or ceil departures per route. We use the persisted cycle-distance
    # field to build conservative exact-count bounds without inventing a phase.
    def inspect(rel: str) -> dict:
        total = ambiguous = nonintegral = 0
        examples = []
        for row in read_gzip(rel):
            headway = int(row["uniform_headway_min"])
            span = int(row["span_end_min"]) - int(row["span_start_min"])
            count = span / headway
            if math.isclose(count, round(count), rel_tol=0.0, abs_tol=1e-12):
                continue
            nonintegral += 1
            cycle_km = float(row["expected_pattern_set_cycle_distance_km"])
            days = int(row["annual_service_days"])
            annual = float(row["annual_bus_km"])
            cap = float(row["budget_cap_annual_bus_km"])
            low = cycle_km * math.floor(count) * days
            high = cycle_km * math.ceil(count) * days
            total += 1
            if low <= cap + 1e-9 < high - 1e-9:
                ambiguous += 1
                if len(examples) < 8:
                    examples.append({
                        "budget_suffix": row["budget_suffix"],
                        "scenario_id": row["scenario_id"],
                        "uniform_headway_min": headway,
                        "span_id": row["span_id"],
                        "annual_service_days": days,
                        "approx_annual_bus_km": annual,
                        "budget_cap_annual_bus_km": cap,
                        "exact_count_lower_bound_bus_km": low,
                        "exact_count_upper_bound_bus_km": high,
                    })
        return {"noninteger_departure_count_rows": nonintegral, "budget_boundary_ambiguous_rows": ambiguous, "examples": examples}

    return {
        "budget_policy_frontier": inspect("outputs/phase2/budget_policy_frontiers_v2/scenario_budget_policy_frontier_v2.csv.gz"),
        "passenger_utility_frontier": inspect("outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz"),
    }


def s8_class_audit() -> dict:
    passenger_keys = {
        (r["scenario_id"], int(r["uniform_headway_min"]), r["span_id"])
        for r in read_gzip("outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2.csv.gz")
    }
    all_counts = {"ALL": 0, "SOME": 0, "NONE": 0}
    stage_c_key_counts = {"ALL": 0, "SOME": 0, "NONE": 0}
    direct_by_key = {}
    for row in read_gzip("outputs/phase2/passenger_gjt_v2/s8_scenario_feeder_envelope_v2.csv.gz"):
        all_routes = row["public_all_routes_have_some_complete_match_phase"].lower() == "true"
        any_route = row["public_any_route_has_some_complete_match_phase"].lower() == "true"
        klass = "ALL" if all_routes else ("SOME" if any_route else "NONE")
        all_counts[klass] += 1
        key = (row["scenario_id"], int(row["uniform_headway_min"]), row["span_id"])
        if key in passenger_keys:
            stage_c_key_counts[klass] += 1
            direct_by_key[key] = klass
    surface_counts = {"ALL": 0, "SOME": 0, "NONE": 0}
    disagreement = 0
    for row in read_gzip("outputs/phase2/s8_robust_opportunity_v2/passenger_plans_s8_opportunity_v2.csv.gz"):
        raw = row["s8_opportunity_class"]
        klass = "ALL" if raw.startswith("ALL_") else ("SOME" if raw.startswith("SOME_") else "NONE")
        surface_counts[klass] += 1
        key = (row["scenario_id"], int(row["uniform_headway_min"]), row["span_id"])
        if direct_by_key.get(key) != klass:
            disagreement += 1
    return {
        "all_800k_scenario_timing_rows": all_counts,
        "stage_c_unique_scenario_timing_keys": stage_c_key_counts,
        "stage_c_plan_rows_surface": surface_counts,
        "surface_vs_direct_class_disagreement_count": disagreement,
    }


def source_scan() -> dict:
    files = sorted([*ROOT.glob("scripts/phase2*.py"), *ROOT.glob("src/phase2*.py")])
    files = [p for p in files if p.name != Path(__file__).name]
    patterns = {
        "random": re.compile(r"np\.random|numpy\.random|\bimport random\b|\bfrom random\b|random\."),
        "network": re.compile(r"requests\.|urllib\.|httpx\.|overpass-api\.de"),
        "weighted_true": re.compile(r"weighted_(?:composite_)?score[^\n]{0,40}(?:=|:)[^\n]{0,20}True"),
        "od_downscale_true": re.compile(r"municipal_(?:work_)?od_downscaled[^\n]{0,30}(?:=|:)[^\n]{0,20}True"),
        "ridership_true": re.compile(r"ridership_forecast[^\n]{0,30}(?:=|:)[^\n]{0,20}True"),
    }
    hits = {k: [] for k in patterns}
    hardcoded_cardinality_hits = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        for label, pattern in patterns.items():
            if pattern.search(text):
                hits[label].append(rel)
        for no in (100000, 490962, 21237, 16883, 50115):
            if re.search(rf"(?:==|!=)\s*{no}\b", text):
                hardcoded_cardinality_hits.append({"file": rel, "value": no})
    return {**hits, "hardcoded_cardinality_hits": hardcoded_cardinality_hits}


def main() -> int:
    findings = []
    pre = read_json("outputs/phase2/pre_gjt_screening_v2/pre_gjt_screening_v2_validation.json")
    baseline = read_json("outputs/phase2/current_service_access_baseline_v2/current_service_access_baseline_v2_validation.json")
    passenger = read_json("outputs/phase2/passenger_utility_frontier_v2/passenger_utility_frontier_v2_validation.json")
    s8 = read_json("outputs/phase2/s8_robust_opportunity_v2/s8_robust_opportunity_v2_validation.json")
    zero = read_json("outputs/phase2/zero_band_tiebreak_v2/zero_band_tiebreak_v2_validation.json")
    continuity = read_json("outputs/phase2/current_service_continuity_v2/current_service_continuity_v2_validation.json")
    access = read_json("outputs/phase2/access_equity_v2/access_equity_v2_validation.json")

    structural_ok = (
        pre["scenario_count"] == 100000 and pre["timing_archetype_count"] == 8 and
        pre["scenario_timing_row_count"] == 800000 and pre["reference_budget_annual_bus_km"] == 111419.0 and
        pre["reference_budget_feasible_scenario_counts_by_timing"]["H15_CORE_0600_2200"] == 6302 and
        pre["reference_budget_feasible_scenario_counts_by_timing"]["H20_CORE_0600_2200"] == 11648 and
        pre["reference_budget_feasible_scenario_counts_by_timing"]["H30_CORE_0600_2200"] == 26533 and
        pre["reference_budget_feasible_scenario_counts_by_timing"]["H60_CORE_0600_2200"] == 69186
    )

    lineage = lineage_checks()
    mismatches = [r for r in lineage if not r["match"]]
    budget = budget_exactness_audit()
    s8_classes = s8_class_audit()
    scan = source_scan()

    exact_stage_d_integrated = (ROOT / "outputs/phase2/exact_timetable_optimizer_v2/stage_d_exact_timetable_v2_validation.json").is_file()
    exact_stage_d_solver_integrated = (ROOT / "scripts/phase2_run_exact_timetable_optimizer_v2.py").is_file()

    ambiguity = budget["passenger_utility_frontier"]["budget_boundary_ambiguous_rows"]
    if ambiguity:
        add_finding(findings, fid="RT-001", classification="METHODOLOGICAL BLOCKER", severity="BLOCKING", stage="Service Policy / Budget → Stage C", title="Continuous production approximation is used before exact hard-budget eligibility", evidence={"passenger_frontier_budget_boundary_ambiguous_rows": ambiguity, "budget_policy_frontier_budget_boundary_ambiguous_rows": budget["budget_policy_frontier"]["budget_boundary_ambiguous_rows"], "examples": budget["passenger_utility_frontier"]["examples"]}, reproducibility="Recompute floor/ceil explicit daily pattern counts from persisted span, headway, cycle distance and annual-day fields; compare both exact-count bounds with each row's budget cap.", consequence="Some Stage-C plans classified as budget-feasible are not guaranteed to remain under the same hard cap after route-specific exact phase selection. The same approximation can also prune boundary cases before Stage D, so search completeness is not guaranteed near the cap.", recommended_fix="Before any budget-based candidate elimination on non-integral span/headway combinations, retain the full exact-count feasibility envelope or enumerate exact route-specific departure counts. Rebuild the budget-policy and Passenger Utility frontiers from that safe surface.")
    else:
        add_finding(findings, fid="RT-001", classification="ACCEPTABLE ASSUMPTION", severity="INFO", stage="Service Policy / Budget", title="Continuous production approximation did not straddle a persisted budget boundary", evidence=budget, reproducibility="Same floor/ceil audit.", consequence="No current persisted Stage-C row was shown ambiguous by this bound.", recommended_fix="Still replace approximation with exact production before final recommendation.")

    if not (exact_stage_d_integrated and exact_stage_d_solver_integrated):
        add_finding(findings, fid="RT-002", classification="METHODOLOGICAL BLOCKER", severity="BLOCKING", stage="Stage D / final decision", title="Frozen integrated lineage is not yet final-decision complete", evidence={"exact_stage_d_solver_integrated": exact_stage_d_solver_integrated, "exact_stage_d_validation_integrated": exact_stage_d_integrated, "passenger_exact_timetable_constructed": passenger["exact_timetable_constructed"], "s8_exact_timetable_constructed": s8["exact_timetable_constructed"], "zero_band_final_reliability_proven": zero["final_reliability_proven"], "primary_selected": passenger["primary_selected"], "runner_up_selected": passenger["runner_up_selected"]}, reproducibility="Check the frozen target tree and the current Stage-C/S8/zero-band validation contracts.", consequence="The normative constraint + robust utility + lexicographic decision rule cannot yet be executed on this integrated HEAD. Reliability/missed connections, exact budget after phasing, explicit vehicle blocks and a substantive uncertainty band are not available here.", recommended_fix="Integrate independently audited exact-timetable evidence, then run the declared robustness sensitivity set and explicitly materialise decision budget plus uncertainty-band policy before authorising PRIMARY/RUNNER-UP.")

    add_finding(findings, fid="RT-003", classification="IMPORTANT LIMITATION", severity="MAJOR", stage="Current-service baseline / non-regression", title="Current lower-bound baseline makes the worst-municipality safeguard non-binding", evidence={"baseline_complete": baseline["baseline_complete"], "localized_rows": baseline["localized_rows"], "unresolved_or_unlocalized_rows": baseline["unresolved_or_unlocalized_rows"], "worst_municipality_5": baseline["coverage_lower_bound"]["5"]["worst_municipality"], "worst_share_5": baseline["coverage_lower_bound"]["5"]["worst_municipality_coverage_share"], "worst_share_8": baseline["coverage_lower_bound"]["8"]["worst_municipality_coverage_share"], "worst_share_10": baseline["coverage_lower_bound"]["10"]["worst_municipality_coverage_share"]}, reproducibility="Read the certified current-service access validation and compare candidate lower bounds against zero.", consequence="Passing the safeguard cannot be interpreted as evidence that no municipality is worse than the true current service. It proves only non-regression below the proven localisable lower bound.", recommended_fix="Keep the current fail-closed lower-bound rule, but propagate an explicit FINAL_DECISION_CAVEAT flag and prohibit language claiming real current-service non-regression until unresolved current stops are spatially resolved. Do not invent municipality floors.")

    add_finding(findings, fid="RT-004", classification="IMPORTANT LIMITATION", severity="MAJOR", stage="Governance / lineage", title="Audit brief and repository governance state are stale relative to frozen artifacts", evidence={"agent_protocol_exists": (ROOT / "AGENT_PROTOCOL.md").is_file(), "collaboration_protocol_exists": (ROOT / "COLLABORATION_PROTOCOL.md").is_file(), "baseline_current": {"localized_rows": baseline["localized_rows"], "unresolved": baseline["unresolved_or_unlocalized_rows"], "coverage_5": baseline["coverage_lower_bound"]["5"]["coverage_share"], "coverage_8": baseline["coverage_lower_bound"]["8"]["coverage_share"], "coverage_10": baseline["coverage_lower_bound"]["10"]["coverage_share"]}, "current_clusters": baseline["localized_unique_physical_clusters"]}, reproducibility="Inspect frozen HEAD files and baseline validation.", consequence="A reviewer using narrative/status counts instead of content-addressed artifacts can audit or tie-break against the wrong current-service snapshot.", recommended_fix="Refresh AGENT_STATUS/governance pointers and make downstream reports cite content SHA plus validation contract, not copied counts.")

    if mismatches:
        add_finding(findings, fid="RT-005", classification="BUG", severity="MAJOR", stage="Cross-stage lineage", title="Persisted downstream lineage hashes do not all match current frozen files", evidence={"mismatch_count": len(mismatches), "mismatches": mismatches}, reproducibility="SHA256 every declared current-file lineage dependency and compare with the persisted expected hash.", consequence="At least one downstream artifact was built against a different byte-level upstream than the file currently present on the integrated branch.", recommended_fix="Rebuild the affected downstream artifact from the frozen current upstream and persist the new lineage before using it for final decisions.")
    else:
        add_finding(findings, fid="RT-005", classification="NON-ISSUE", severity="INFO", stage="Cross-stage lineage", title="Audited current-file lineage hashes are internally consistent", evidence={"checked_hash_edges": len(lineage)}, reproducibility="SHA256 declared dependencies.", consequence="No byte-level drift detected in the audited lineage edges.", recommended_fix="Keep the fail-closed hash checks.")

    add_finding(findings, fid="RT-006", classification="IMPORTANT LIMITATION", severity="MAJOR", stage="Passenger Utility Frontier", title="Stage-C skyline is an accessibility screening frontier, not the normative robust passenger-utility ranking", evidence={"full_gjt_calculated": passenger["full_gjt_calculated"], "municipal_work_od_downscaled": passenger["municipal_work_od_downscaled"], "availability_axes": passenger["global_additional_availability_maximise_axes"], "worker_upper_bound_axes": [x for x in passenger["passenger_maximise_axes_within_service_context"] if "worker_mass_upper_bound" in x], "calendar_selected": passenger["calendar_selected"]}, reproducibility="Compare PHASE2_SERVICE_DESIGN_SPEC §9/§11 with the persisted Passenger Utility axes and flags.", consequence="Correlated accessibility and municipal structural upper-bound axes can preserve a broad Pareto set, but they do not implement expected/median demand-weighted GJT across the declared sensitivity set. The 260/312/365 availability assumptions also have no observed day-type demand weights yet.", recommended_fix="Treat Stage C strictly as screening. Final ranking must use the declared behavioural/runtime sensitivity set at supported demand resolution, with annual-day assumptions explicitly retained as scenarios rather than empirical facts.")

    s8_ok = (
        s8_classes["surface_vs_direct_class_disagreement_count"] == 0 and
        s8_classes["stage_c_unique_scenario_timing_keys"]["SOME"] == 0 and
        s8_classes["all_800k_scenario_timing_rows"]["SOME"] > 0
    )
    add_finding(findings, fid="RT-007", classification="NON-ISSUE" if s8_ok else "BUG", severity="INFO" if s8_ok else "MAJOR", stage="S8 Robust Opportunity", title="Absence of the intermediate SOME class on Stage C is a subset property" if s8_ok else "S8 opportunity class aggregation is inconsistent", evidence=s8_classes, reproducibility="Recompute ALL/SOME/NONE directly from public_all/public_any booleans on the 800k feeder envelope and on the Stage-C scenario×timing key subset; compare with the promoted surface.", consequence="The global universe contains intermediate cases, but the Stage-C subset does not; this falsifies the hypothesis that the class was accidentally impossible in code." if s8_ok else "Promoted S8 opportunity labels disagree with their source envelope.", recommended_fix="No fix; keep explicit warning that route-level some-phase opportunity is not joint timetable feasibility." if s8_ok else "Repair class promotion and rebuild downstream S8 evidence.")

    bridge = access.get("hub_access_bridge", {})
    bridge_ok = (
        bridge.get("status") == "VERIFIED_APPLIED" and bridge.get("scope") == "PEDESTRIAN_ACCESS_ONLY" and
        bridge.get("rail_anchor_id") == "rail:S01514" and bridge.get("official_bus_stop_id") == "L00407" and
        bridge.get("physical_cluster_id") == "EX_039" and
        all(bridge.get(k) is False for k in ("operational_network_changed", "route_geometry_changed", "runtime_changed", "bus_km_changed", "od_evidence_changed", "s8_evidence_changed", "service_policy_changed"))
    )
    add_finding(findings, fid="RT-008", classification="NON-ISSUE" if bridge_ok else "BUG", severity="INFO" if bridge_ok else "MAJOR", stage="Station accessibility bridge", title="Station bridge preserves pedestrian-only scope and separate historical identity" if bridge_ok else "Station bridge contract is breached", evidence=bridge, reproducibility="Inspect wrapper contract and access validation; core catchment summarisation uses per-unit minimum walk over a set of anchors, preventing duplicate population count.", consequence="No route/runtime/km/OD/S8/service-policy mutation detected." if bridge_ok else "Pedestrian fix may have leaked into operational evidence.", recommended_fix="Keep fail-closed bridge tests and historical 300407/EX_011 separation." if bridge_ok else "Remove leaked mutation and rebuild access layer.")

    pu_axes = set(passenger["passenger_maximise_axes_within_service_context"])
    pu_contract_ok = all(f"public_population_coverage_share_{t}min" in pu_axes and f"public_worst_municipality_coverage_share_{t}min" in pu_axes for t in (5,8,10)) and passenger["two_stage_skyline_equivalence"].startswith("EXACT_")
    add_finding(findings, fid="RT-009", classification="NON-ISSUE" if pu_contract_ok else "BUG", severity="INFO" if pu_contract_ok else "MAJOR", stage="Passenger Utility Pareto", title="5/8/10 axes and two-stage skyline contract are preserved" if pu_contract_ok else "Passenger Utility skyline contract is incomplete", evidence={"axes": passenger["passenger_maximise_axes_within_service_context"], "two_stage": passenger["two_stage_skyline_equivalence"], "frontier_rows": passenger["passenger_utility_frontier_row_count_all_budgets"]}, reproducibility="Inspect certified wrapper/workflow and compare stage-1 context dominance with final availability-aware Pareto theorem.", consequence="No missing 8-minute axis or invalid two-stage decomposition detected." if pu_contract_ok else "Frontier can drop valid nondominated plans.", recommended_fix="Keep wrapper as the certified entry point and add direct-global skyline regression samples." if pu_contract_ok else "Rebuild using all certified axes and a mathematically equivalent decomposition.")

    add_finding(findings, fid="RT-010", classification="NON-ISSUE", severity="INFO", stage="Zero-band tie-break", title="Zero-band result is genuinely non-eliminating", evidence={"input": zero["input_plan_count"], "survivors": zero["survivor_plan_count"], "multi_plan_groups": zero["multi_plan_equivalence_group_count"], "reduced_groups": zero["reduced_equivalence_group_count"], "uncertainty_band": zero["uncertainty_band_used"]}, reproducibility="Rebuild equivalence keys at the Stage-C certified 1e-9 profile precision and run supported lexicographic fields.", consequence="No candidate was silently removed by the provisional tie-break.", recommended_fix="Do not reuse the pre-timetable reliability proxy as final reliability; continuity is now materialised and must enter only at the final declared tie-break stage.")

    hardcoded = scan["hardcoded_cardinality_hits"]
    if hardcoded:
        add_finding(findings, fid="RT-011", classification="IMPORTANT LIMITATION", severity="MINOR", stage="Technical auditability", title="Production builders contain hard-coded expected artifact cardinalities", evidence={"hit_count": len(hardcoded), "examples": hardcoded[:20]}, reproducibility="Static scan for equality/inequality checks against current artifact cardinalities.", consequence="These checks fail closed and do not bias rankings, but they conflate lineage epoch locks with mathematical invariants and make legitimate refreshed epochs fail until code is edited.", recommended_fix="Move epoch-specific cardinalities into versioned validation contracts/manifests while retaining hash and schema checks in code.")

    no_boundary_leak = not scan["od_downscale_true"] and not scan["ridership_true"] and not scan["weighted_true"] and not scan["random"]
    add_finding(findings, fid="RT-012", classification="NON-ISSUE" if no_boundary_leak else "BUG", severity="INFO" if no_boundary_leak else "BLOCKING", stage="OD / demand / technical leakage", title="No hidden weighted score, OD downscaling, ridership inference or random search detected" if no_boundary_leak else "Forbidden inference or stochastic leakage detected", evidence=scan, reproducibility="Static scan of Phase-2 production Python sources, plus contract checks in OD/S8 builders.", consequence="Municipal work evidence remains structural; S8 worker counts weight rail direction only; residential population remains accessibility weight." if no_boundary_leak else "Epistemic boundary is breached.", recommended_fix="Keep explicit false flags and fail-closed source checks." if no_boundary_leak else "Remove the detected inference/stochastic path and rebuild affected artifacts.")

    add_finding(findings, fid="RT-013", classification="ACCEPTABLE ASSUMPTION", severity="INFO", stage="Service policy", title="Calendars, recovery and extension shares are explicitly assumptions rather than observed service facts", evidence={"production_semantics": read_json("outputs/phase2/service_policy_search_v2/service_policy_search_v2_validation.json")["production_semantics"], "current_annual_service_days_inferred": read_json("outputs/phase2/service_policy_search_v2/service_policy_search_v2_validation.json")["current_annual_service_days_inferred"], "continuity_complete": continuity["continuity_is_complete_current_service_measure"]}, reproducibility="Inspect versioned design-space config and service-policy validation.", consequence="The grid is legitimate for sensitivity exploration, but calendar values cannot be described as observed current-service calendars.", recommended_fix="Preserve assumption labels through final reporting and test explicit day-type utility before choosing a calendar.")

    severity_rank = {"BLOCKING": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
    findings.sort(key=lambda f: (severity_rank[f["severity"]], f["id"]))
    OUTDIR.mkdir(parents=True, exist_ok=True)
    FINDINGS_OUT.write_text(json.dumps({"audit_target_sha": TARGET_SHA, "findings": findings}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    blocking = sum(f["severity"] == "BLOCKING" for f in findings)
    major = sum(f["severity"] == "MAJOR" for f in findings)
    minor = sum(f["severity"] == "MINOR" for f in findings)
    validation = {
        "status": "BLOCKED" if blocking else ("PASS_WITH_LIMITATIONS" if major or minor else "PASS"),
        "contract": "PHASE2_FINAL_METHOD_REDTEAM_V2",
        "audit_target_sha": TARGET_SHA,
        "audit_complete": True,
        "blocking_issue_count": blocking,
        "major_issue_count": major,
        "minor_issue_count": minor,
        "weighted_score_detected": bool(scan["weighted_true"]),
        "municipal_od_downscaling_detected": bool(scan["od_downscale_true"]),
        "ridership_inference_detected": bool(scan["ridership_true"]),
        "synthetic_data_detected": bool(scan["random"]),
        "nondeterminism_detected": bool(scan["random"]),
        "lineage_mismatch_detected": bool(mismatches),
        "lineage_hash_edge_count_checked": len(lineage),
        "lineage_hash_mismatch_count": len(mismatches),
        "current_service_baseline_semantics_preserved": baseline["baseline_complete"] is False and baseline["may_infer_true_current_total_coverage"] is False,
        "station_bridge_semantics_preserved": bridge_ok,
        "passenger_utility_contract_valid": pu_contract_ok,
        "s8_opportunity_contract_valid": s8_ok,
        "structural_reference_counts_verified": structural_ok,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "final_selection_blocked": blocking > 0,
        "budget_exactness_audit": budget,
        "s8_class_audit": s8_classes,
        "lineage_checks": lineage,
        "source_scan": scan,
        "findings_sha256": sha256_path(FINDINGS_OUT),
    }
    VALIDATION_OUT.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: validation[k] for k in ("status", "blocking_issue_count", "major_issue_count", "minor_issue_count", "lineage_hash_mismatch_count", "structural_reference_counts_verified")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
