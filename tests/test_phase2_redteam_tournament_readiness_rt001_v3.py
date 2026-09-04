from __future__ import annotations

from pathlib import Path

from scripts.phase2_redteam_tournament_readiness_rt001_v3 import (
    CONTRACT,
    STATUS,
    build,
    build_parser,
    scan_frontier_consumers,
)


def repo_args(tmp_path: Path):
    return build_parser().parse_args(["--output-dir", str(tmp_path)])


def test_certified_codex_tournament_chain_passes_fail_closed_redteam(tmp_path: Path) -> None:
    result = build(repo_args(tmp_path))

    assert result["status"] == STATUS
    assert result["contract"] == CONTRACT
    assert result["audit_pass"] is True
    assert result["input_context_count"] == 16_495
    assert result["frontier_context_count"] == 12_284
    assert result["dominated_context_count"] == 4_211
    assert result["legacy_rows_collapsed_by_v2_identity"] == 6_961
    assert result["pareto_dimension_count"] == 29
    assert result["lower_bound_axis_count"] == 3
    assert result["downstream_frontier_executable_consumer_count"] == 0

    for field in (
        "final_tournament_execution_ready",
        "final_selection_authorized",
        "primary_selection_authorised",
        "runner_up_selection_authorised",
        "decision_budget_selected",
        "uncertainty_band_selected",
        "calendar_selected",
        "recovery_selected",
        "weighted_composite_score",
        "manufactured_demand_weighted_gjt",
        "manufactured_missed_connection_probability",
        "stage_e_engineering_retention_reinterpreted_as_probability",
        "municipal_od_spatially_downscaled",
        "legacy_v2_finalizer_authorized",
        "legacy_v2_finalizer_invoked",
        "frontier_is_ranking",
        "frontier_is_shortlist",
        "frontier_membership_may_authorize_pruning",
        "nonfrontier_pruning_authorized",
        "lower_bound_axes_establish_true_system_dominance",
    ):
        assert result[field] is False, field

    assert result["frontier_is_descriptive_only"] is True
    assert result["required_downstream_rule"].startswith("PRESERVE_ALL_16495_CONTEXTS")


def test_redteam_rebuild_is_byte_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    build(repo_args(left))
    build(repo_args(right))

    for name in (
        "tournament_readiness_redteam_findings_rt001_v3.csv",
        "tournament_readiness_redteam_rt001_v3_validation.json",
    ):
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_frontier_consumer_scan_fails_open_world_pruning_path(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    src = tmp_path / "src"
    scripts.mkdir()
    src.mkdir()
    (scripts / "phase2_build_nondeci_tournament_frontier_rt001_v3.py").write_text(
        "name = 'pareto_frontier_member'\n", encoding="utf-8"
    )
    redteam = scripts / "redteam.py"
    redteam.write_text("# audit\n", encoding="utf-8")
    (src / "downstream_selector.py").write_text(
        "INPUT = 'non_decisional_pareto_membership_rt001_v3.csv.gz'\n", encoding="utf-8"
    )

    assert scan_frontier_consumers(tmp_path, redteam) == ["src/downstream_selector.py"]
