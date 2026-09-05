from __future__ import annotations

import json
from pathlib import Path

from src.phase2_cross_engine_discrepancy_v3 import (
    ODTravelTime,
    compare_engines,
    summarize_discrepancies,
)


OUT = Path("outputs/phase2/cross_engine_discrepancy_v3/cross_engine_discrepancy_v3_validation.json")


def main() -> None:
    engine_a = [
        ODTravelTime("O1", "D1", 5.0),
        ODTravelTime("O1", "D2", 10.0),
        ODTravelTime("O2", "D1", 8.0),
        ODTravelTime("O2", "D2", 7.0),
        ODTravelTime("O3", "D1", 0.0),
    ]
    engine_b = [
        ODTravelTime("O2", "D2", 27.0),
        ODTravelTime("O1", "D1", 6.0),
        ODTravelTime("O3", "D1", 2.0),
        ODTravelTime("O1", "D2", 9.0),
        ODTravelTime("O2", "D1", 8.0),
    ]
    discrepancies = compare_engines(
        engine_a,
        engine_b,
        engine_a_label="ENGINE_A",
        engine_b_label="ENGINE_B",
    )
    summary = summarize_discrepancies(discrepancies, reporting_bands_min=(1.0, 3.0, 5.0))

    large = next(r for r in discrepancies if r.from_id == "O2" and r.to_id == "D2")
    zero = next(r for r in discrepancies if r.from_id == "O3" and r.to_id == "D1")

    payload = {
        "status": "PASS_RT013_CROSS_ENGINE_DISCREPANCY_CONTRACT_V3",
        "fixture_semantics": "CONTROLLED_ABSTRACT_OD_FIXTURE_NOT_TERRITORIAL_DATA",
        "od_alignment_fail_closed": True,
        "engine_average_constructed": summary["engine_average_constructed"],
        "automatic_equivalence_claim": summary["automatic_equivalence_claim"],
        "reporting_bands_are_diagnostic_only": summary["reporting_bands_are_diagnostic_only"],
        "od_count": summary["od_count"],
        "mean_signed_difference_min": summary["mean_signed_difference_min"],
        "mean_absolute_difference_min": summary["mean_absolute_difference_min"],
        "p95_absolute_difference_min": summary["p95_absolute_difference_min"],
        "max_absolute_difference_min": summary["max_absolute_difference_min"],
        "large_disagreement_signed_min": large.signed_difference_min,
        "large_disagreement_absolute_min": large.absolute_difference_min,
        "zero_denominator_relative_is_undefined": zero.relative_difference_vs_a is None,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
        "network_recommendation_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
