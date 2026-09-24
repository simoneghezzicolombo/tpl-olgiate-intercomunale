#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

STATUS = "PASS_PHASE2_V3_DECISION_PACKET_A_VALIDATION"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(packet_path: Path, frontier_config_path: Path, stage_d_path: Path, frontier_validation_path: Path, budget_path: Path):
    packet = load_json(packet_path)
    frontier_cfg = load_json(frontier_config_path)
    stage_d = load_json(stage_d_path)
    frontier = load_json(frontier_validation_path)

    assert packet["status"] == "READY_FOR_HUMAN_POLICY_INPUT"
    assert packet["final_selection_authorized"] is False
    assert packet["primary_selected"] is False
    assert packet["runner_up_selected"] is False
    assert packet["weighted_composite_score"] is False
    assert packet["human_choices"]["pathway"]["selection"] == "PENDING_HUMAN_DECISION"
    assert packet["human_choices"]["decision_budget"]["selection"] == "PENDING_HUMAN_DECISION"
    assert packet["human_choices"]["uncertainty_semantics"]["selection"] == "PENDING_HUMAN_DECISION"
    assert packet["human_choices"]["no_weight_rule"]["selection"] == "PENDING_HUMAN_DECISION"

    assert frontier_cfg["contract"] == "PHASE2_NON_DECISIONAL_CERTIFIED_METRIC_PARETO_FRONTIER_RT001_V3"
    expected_dims = {d["field"]: d["direction"] for d in frontier_cfg["dimensions"]}
    criteria = packet["human_choices"]["no_weight_rule"]["rule"]["ordered_criteria"]
    actual_dims = {d["field"]: d["direction"] for d in criteria}
    assert len(criteria) == 29
    assert len(actual_dims) == 29
    assert actual_dims == expected_dims, "Decision rule must cover exactly the certified 29 dimensions with certified directions"

    assert stage_d["status"] == "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
    assert stage_d["stage_c_plan_context_count"] == 16495
    assert frontier["status"] == "PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3"
    assert frontier["input_context_count"] == 16495
    assert frontier["frontier_context_count"] == 12284
    assert frontier["dominated_context_count"] == 4211
    assert frontier["weighted_composite_score"] is False
    assert frontier["decision_budget_selected"] is False

    with budget_path.open(encoding="utf-8-sig", newline="") as handle:
        budget_rows = list(csv.DictReader(handle))
    assert len(budget_rows) == 6
    caps = [float(r["annual_bus_km_cap"]) for r in budget_rows]
    packet_caps = [float(r["annual_bus_km_cap"]) for r in packet["budget_options"]]
    assert len(packet_caps) == 6
    for a, b in zip(packet_caps, caps):
        assert abs(a - b) < 1e-6

    stage_d_counts = stage_d["eligible_context_count_by_budget"]
    suffix_to_stage_d = {
        "m20pct": "m20pct",
        "m10pct": "m10pct",
        "reference": "reference",
        "p10pct": "p10pct",
        "p20pct": "p20pct",
        "p30pct": "p30pct",
    }
    for row in packet["budget_options"]:
        suffix = row["budget_suffix"]
        assert row["eligible_context_count"] == stage_d_counts[suffix_to_stage_d[suffix]]
        complete = frontier["partition_summary"][f"{suffix}|BIDIRECTIONAL_ENGINEERING_RETENTION_AVAILABLE"]
        incomplete = frontier["partition_summary"][f"{suffix}|NO_PLANNED_BUS_TO_RAIL_METRIC"]
        assert row["bidirectional_engineering_context_count"] == complete["input_context_count"]
        assert row["no_planned_bus_to_rail_metric_context_count"] == incomplete["input_context_count"]
        assert row["descriptive_frontier_context_count"] == complete["frontier_context_count"] + incomplete["frontier_context_count"]
        assert row["eligible_context_count"] == complete["input_context_count"] + incomplete["input_context_count"]

    assert sum(r["eligible_context_count"] for r in packet["budget_options"]) == 16495
    assert sum(r["descriptive_frontier_context_count"] for r in packet["budget_options"]) == 12284

    assert packet["certified_sources"]["final_decision_sufficiency_gate"]["v3_technical_open_data_requirement_count"] == 0
    assert packet["certified_sources"]["alpha_gjt_set_bounds"]["finite_upper_bound_row_count"] == 0
    assert packet["certified_sources"]["alpha_gjt_set_bounds"]["unbounded_upper_bound_row_count"] == 60000
    assert packet["certified_sources"]["targeted_gjt_redteam_a"]["blocking_issue_count"] == 0

    return {
        "status": STATUS,
        "contract": "PHASE2_V3_DECISION_PACKET_A_STATIC_SOURCE_VALIDATION",
        "validation_pass": True,
        "human_decision_required": True,
        "final_selection_authorized": False,
        "certified_dimension_count": len(expected_dims),
        "decision_rule_dimension_count": len(actual_dims),
        "dimension_set_and_directions_exact_match": True,
        "budget_option_count": len(packet["budget_options"]),
        "budget_caps_match_certified_source": True,
        "eligible_context_count_total": sum(r["eligible_context_count"] for r in packet["budget_options"]),
        "descriptive_frontier_context_count_total": sum(r["descriptive_frontier_context_count"] for r in packet["budget_options"]),
        "v3_technical_open_data_requirement_count": 0,
        "gjt_interval_dominance_decision_signal_available": False,
        "weighted_composite_score": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "next_step": "HUMAN_APPROVE_OR_EDIT_PATHWAY_BUDGET_UNCERTAINTY_SEMANTICS_AND_NO_WEIGHT_RULE"
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--packet", type=Path, default=Path("config/phase2_v3_decision_packet_a.json"))
    p.add_argument("--frontier-config", type=Path, default=Path("config/phase2_nondeci_tournament_frontier_rt001_v3.json"))
    p.add_argument("--stage-d", type=Path, default=Path("outputs/phase2/stage_d_exact_rt001_v3/stage_d_exact_rt001_v3_validation.json"))
    p.add_argument("--frontier-validation", type=Path, default=Path("outputs/phase2/non_decisional_tournament_frontier_rt001_v3/non_decisional_pareto_frontier_rt001_v3_validation.json"))
    p.add_argument("--budget", type=Path, default=Path("outputs/phase2/budget_envelopes.csv"))
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()
    result = validate(args.packet, args.frontier_config, args.stage_d, args.frontier_validation, args.budget)
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
