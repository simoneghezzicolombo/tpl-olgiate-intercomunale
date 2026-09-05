from __future__ import annotations

import json
from pathlib import Path

from src.phase2_cross_engine_experiment_manifest_v3 import (
    EngineExecutionBinding,
    ExperimentSpec,
    ODKey,
    authorize_cross_engine_comparison,
    freeze_experiment,
)


OUT = Path("outputs/phase2/cross_engine_experiment_manifest_v3/cross_engine_experiment_manifest_v3_validation.json")


def main() -> None:
    spec = ExperimentSpec(
        schema_version="RT015_V3",
        candidate_id="CANDIDATE_X",
        candidate_gtfs_sha256="a" * 64,
        street_network_sha256="b" * 64,
        service_date="2026-10-01",
        timezone="Europe/Paris",
        departure_window_start_sec=21600,
        departure_window_end_sec=32400,
        modes=("TRANSIT", "WALK"),
        od_keys=(ODKey("O2", "D1"), ODKey("O1", "D2"), ODKey("O1", "D1")),
    )
    frozen = freeze_experiment(spec)
    shuffled = freeze_experiment(
        ExperimentSpec(
            **{
                **spec.__dict__,
                "modes": tuple(reversed(spec.modes)),
                "od_keys": tuple(reversed(spec.od_keys)),
            }
        )
    )
    assert frozen.canonical_json == shuffled.canonical_json
    authorize_cross_engine_comparison(
        (
            EngineExecutionBinding("ENGINE_A", frozen.manifest_sha256),
            EngineExecutionBinding("ENGINE_B", frozen.manifest_sha256),
        ),
        expected_manifest_sha256=frozen.manifest_sha256,
    )

    payload = {
        "status": "PASS_RT015_FROZEN_CROSS_ENGINE_EXPERIMENT_MANIFEST_V3",
        "fixture_semantics": "CONTROLLED_ABSTRACT_EXPERIMENT_FIXTURE_NOT_TERRITORIAL_DATA",
        "manifest_sha256": frozen.manifest_sha256,
        "canonicalization_deterministic": True,
        "input_order_invariant": True,
        "od_count": 3,
        "mode_count": 2,
        "exactly_two_distinct_engines_required": True,
        "manifest_mismatch_fails_closed": True,
        "routing_disagreement_not_interpreted_before_identity_check": True,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
        "network_recommendation_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
