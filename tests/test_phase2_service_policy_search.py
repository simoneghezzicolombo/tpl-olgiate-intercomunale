from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.phase2_service_policy_search import (
    decode_policy_mask,
    encode_policy_mask,
    evaluate_policy_for_scenario,
    load_design_space,
)


def design_payload() -> dict:
    return {
        "contract": "PHASE2_SERVICE_POLICY_DESIGN_SPACE_V2",
        "status": "ASSUMPTION_DESIGN_SPACE_NOT_SERVICE_PLAN",
        "uniform_clockface_baseline": True,
        "peak_offpeak_differentiation_in_this_sweep": False,
        "headways_min": [15, 20, 30, 60],
        "spans": [
            {"span_id": "A", "start_min": 360, "end_min": 1320, "status": "ASSUMPTION_DESIGN_SPACE"},
            {"span_id": "B", "start_min": 330, "end_min": 1440, "status": "ASSUMPTION_DESIGN_SPACE"},
        ],
        "annual_service_days": [
            {"calendar_id": "C1", "days": 260, "status": "ASSUMPTION_DESIGN_SPACE_NOT_ACTUAL_CALENDAR"},
            {"calendar_id": "C2", "days": 312, "status": "ASSUMPTION_DESIGN_SPACE_NOT_ACTUAL_CALENDAR"},
            {"calendar_id": "C3", "days": 365, "status": "ASSUMPTION_DESIGN_SPACE_NOT_ACTUAL_CALENDAR"},
        ],
        "recovery_min": [5, 10, 15],
        "scheduled_extension_shares": [0.0, 0.25, 0.5, 1.0],
    }


def test_declared_grid_has_288_policies_and_72_nonextension(tmp_path: Path) -> None:
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design_payload()), encoding="utf-8")
    _, policies = load_design_space(path)
    assert len(policies) == 288
    assert sum(p.extension_share == 0.0 for p in policies) == 72
    assert len({p.policy_id for p in policies}) == 288


def test_nonextension_rejects_nonzero_extension_share(tmp_path: Path) -> None:
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design_payload()), encoding="utf-8")
    _, policies = load_design_space(path)
    policy = next(p for p in policies if p.extension_share == 0.25)
    assert evaluate_policy_for_scenario(
        policy,
        topology_family="single_compact_loop",
        public_cycle_distance_km=20.0,
        public_cycle_runtime_min=40.0,
        public_route_count=1,
        extension_cycle_distance_km=None,
        extension_cycle_runtime_min=None,
    ) is None


def test_scheduled_extension_share_replaces_base_cycle(tmp_path: Path) -> None:
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design_payload()), encoding="utf-8")
    _, policies = load_design_space(path)
    policy = next(
        p for p in policies
        if p.extension_share == 0.5 and p.uniform_headway_min == 30 and p.span_id == "A"
        and p.annual_service_days == 260 and p.recovery_min == 5
    )
    metrics = evaluate_policy_for_scenario(
        policy,
        topology_family="scheduled_extensions",
        public_cycle_distance_km=10.0,
        public_cycle_runtime_min=20.0,
        public_route_count=1,
        extension_cycle_distance_km=18.0,
        extension_cycle_runtime_min=36.0,
    )
    assert metrics is not None
    assert metrics.expected_pattern_set_cycle_distance_km == pytest.approx(14.0)
    assert metrics.expected_pattern_set_cycle_runtime_min == pytest.approx(28.0)
    assert metrics.annual_bus_km == pytest.approx(14.0 * (960 / 30) * 260)
    assert metrics.aggregate_interlinable_fleet_lower_bound == 2


def test_policy_mask_roundtrip_is_lossless() -> None:
    indices = (0, 1, 17, 72, 143, 287)
    mask = encode_policy_mask(indices, policy_count=288)
    assert len(mask) == 72
    assert decode_policy_mask(mask, policy_count=288) == indices
