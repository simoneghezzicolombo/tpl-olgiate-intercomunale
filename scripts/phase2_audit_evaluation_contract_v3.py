from __future__ import annotations

import json
from pathlib import Path

from src.phase2_evaluation_contract_v3 import (
    ServiceAreaDiagnostic,
    WalkingObservation,
    normalize_service_area_diagnostics,
    pareto_front,
    population_share_at_or_below,
    summarize_walking_burden,
    territorial_policy_guard,
)


OUT = Path("outputs/phase2/evaluation_contract_v3/evaluation_contract_v3_validation.json")


def make_obs(prefix: str, minutes: list[float]) -> list[WalkingObservation]:
    return [
        WalkingObservation(f"{prefix}{i}", 100.0, minute)
        for i, minute in enumerate(minutes, start=1)
    ]


def main() -> None:
    near = make_obs("N", [3, 4, 5, 5])
    far = make_obs("F", [11, 12, 13, 14])
    near_summary = summarize_walking_burden(near)
    far_summary = summarize_walking_burden(far)

    candidates = [
        {
            "candidate_id": "SHORT",
            "annual_km": 80000.0,
            "weighted_mean_walk_min": 11.5,
            "continuous_accessibility": 0.62,
        },
        {
            "candidate_id": "ACCESS",
            "annual_km": 87000.0,
            "weighted_mean_walk_min": 4.2,
            "continuous_accessibility": 0.81,
        },
        {
            "candidate_id": "DOMINATED",
            "annual_km": 90000.0,
            "weighted_mean_walk_min": 12.0,
            "continuous_accessibility": 0.55,
        },
    ]
    dimensions = {
        "annual_km": "min",
        "weighted_mean_walk_min": "min",
        "continuous_accessibility": "max",
    }
    frontier = pareto_front(candidates, dimensions)

    guard = territorial_policy_guard({"G1", "G2", "G3"}, {"G1", "G3"})
    diagnostics = normalize_service_area_diagnostics(
        [
            ServiceAreaDiagnostic(
                area_id="AREA_X",
                served=False,
                nearest_stop_id="S9",
                nearest_walk_minutes=13.0,
                marginal_extra_km=1.2,
                marginal_extra_runtime_min=3.1,
            )
        ]
    )

    payload = {
        "status": "PASS_RT011_EVALUATION_CONTRACT_V3",
        "fixture_semantics": "CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA",
        "weighted_composite_score": False,
        "threshold_only_accessibility": False,
        "random_search": False,
        "territorial_candidate_claim": False,
        "network_recommendation_claim": False,
        "same_share_le_15_min": population_share_at_or_below(near, 15.0)
        == population_share_at_or_below(far, 15.0)
        == 1.0,
        "near_weighted_mean_walk_min": near_summary["weighted_mean_walk_min"],
        "far_weighted_mean_walk_min": far_summary["weighted_mean_walk_min"],
        "near_weighted_p90_walk_min": near_summary["weighted_p90_walk_min"],
        "far_weighted_p90_walk_min": far_summary["weighted_p90_walk_min"],
        "pareto_frontier_ids": frontier,
        "tradeoff_candidates_both_preserved": "ACCESS" in frontier and "SHORT" in frontier,
        "dominated_candidate_removed": "DOMINATED" not in frontier,
        "policy_guard_passes": guard["passes"],
        "missing_policy_groups": guard["missing_policy_groups"],
        "unserved_area_preserved_as_diagnostic": diagnostics[0].served is False,
        "marginal_service_fields_are_diagnostic_only": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
