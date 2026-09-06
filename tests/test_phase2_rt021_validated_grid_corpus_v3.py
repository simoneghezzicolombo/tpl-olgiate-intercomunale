from __future__ import annotations

from src import phase2_rt021_validated_grid_corpus_v3 as grid


def test_validated_grid_is_exact_rt006_12_configuration_cartesian_product():
    observed = [
        (
            config["config_id"],
            config["penalty_increment"],
            config["max_runtime_factor"],
            config["max_overlap"],
        )
        for config in grid.VALIDATED_RT006_GRID
    ]
    expected = []
    index = 1
    for penalty in [0.10, 0.20, 0.35]:
        for runtime_factor in [1.25, 1.50]:
            for overlap in [0.75, 0.90]:
                expected.append((f"CFG_{index:02d}", penalty, runtime_factor, overlap))
                index += 1
    assert observed == expected
    assert len(observed) == 12
    assert grid.DEFAULT_GRID_KEY == (0.20, 1.50, 0.90)


def test_sensitivity_union_deduplicates_exact_paths_without_frequency_ranking(monkeypatch):
    empty_default = {
        "corridors": [],
        "generation_audit": [{"generation_round": 0}],
    }

    def path(edge_ids, runtime, distance, generation_round):
        return {
            "edge_ids": tuple(edge_ids),
            "node_ids": ("N0", "N1"),
            "running_minutes_model": runtime,
            "distance_m": distance,
            "provenance": "BOUNDED_PENALTY_ALTERNATIVE",
            "generation_round": generation_round,
            "physical_node_loop": False,
            "runtime_factor_vs_shortest": 1.1,
            "max_shared_runtime_fraction": 0.5,
            "admissible_for_corridor_pool": True,
            "rejection_reason": "",
        }

    def fake_generate(*args, **kwargs):
        key = (
            round(float(kwargs["penalty_increment"]), 2),
            round(float(kwargs["max_runtime_factor"]), 2),
            round(float(kwargs["max_overlap"]), 2),
        )
        if key in {(0.10, 1.25, 0.75), (0.10, 1.25, 0.90)}:
            corridors = [path(["e1", "e2"], 10.0, 1000.0, 1)]
        elif key == (0.35, 1.50, 0.90):
            corridors = [path(["e3", "e4"], 11.0, 1100.0, 2)]
        else:
            corridors = []
        return {
            "corridors": corridors,
            "generation_audit": [{"generation_round": 0}] + corridors,
        }

    monkeypatch.setattr(
        grid.bounded,
        "generate_bounded_from_frozen_baseline",
        fake_generate,
    )
    result = grid.sensitivity_union_from_frozen_baseline(
        adjacency={},
        rule_index={},
        lookup={},
        source="S",
        target="T",
        baseline_edge_ids=["base"],
        default_result=empty_default,
    )

    assert result["configuration_count"] == 12
    assert result["unique_edge_sequences"] == 2
    assert [tuple(p["edge_ids"]) for p in result["corridors"]] == [
        ("e1", "e2"),
        ("e3", "e4"),
    ]
    assert all(p["provenance"] == grid.SENSITIVITY_PROVENANCE for p in result["corridors"])
    # The repeated e1/e2 path is materialised once. Appearance count is only
    # diagnostic provenance and never a quality score or ranking criterion.
    assert result["configuration_ids_by_path"]["e1;e2"] == ["CFG_01", "CFG_02"]
    assert "appearance_score" not in result
    assert result["union_contract"].endswith("NOT_FREQUENCY_WEIGHTED_NOT_RANKED")


def test_explicit_grid_failure_reason_does_not_claim_physical_unreachability():
    reason = grid.EXPLICIT_GRID_FAILURE_REASON
    assert "VALIDATED_RT006_PARAMETER_GRID" in reason
    assert "UNROUTABLE" not in reason
    assert "NO_ROUTE" not in reason
