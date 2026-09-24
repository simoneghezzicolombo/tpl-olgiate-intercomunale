from decimal import Decimal

from src.phase2_s8_transfer_gap_envelope_v2 import (
    exact_weighted_phase_envelope,
    runtime_parts,
)
from src.phase2_s8_work_transfer_utility_v2 import WorkDirectionWeights


def _weights():
    return WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 697.0, "MILANO": 1185.0},
        return_rail_to_bus={"LECCO": 1185.0, "MILANO": 697.0},
    )


def _phase(b2r_m, b2r_l, r2b_m, r2b_l, unmatched=0):
    out = {}
    for prefix, value in (
        ("vehicle_cycle_to_rail_milano", b2r_m),
        ("vehicle_cycle_to_rail_lecco", b2r_l),
        ("rail_to_bus_milano", r2b_m),
        ("rail_to_bus_lecco", r2b_l),
    ):
        out[f"{prefix}_mean_gap_min"] = value
        out[f"{prefix}_unmatched_count"] = unmatched
    return out


def test_runtime_parts_requires_positive_fraction():
    assert runtime_parts("42.313725198") == (42, Decimal("0.313725198"))
    try:
        runtime_parts("42")
    except ValueError as exc:
        assert "positive fractional" in str(exc)
    else:
        raise AssertionError("Expected integer runtime to fail audited V2 runtime-class guard")


def test_roundtrip_gap_uses_common_phase_and_exact_fraction_translation():
    phases = [
        _phase(10.0, 20.0, 5.0, 7.0),
        _phase(20.0, 10.0, 9.0, 3.0),
    ]
    env_half = exact_weighted_phase_envelope(
        phase_metrics=phases,
        weights=_weights(),
        roundtrip_passenger_supported=True,
        actual_fractional_runtime=Decimal("0.5"),
    )
    env_point8 = exact_weighted_phase_envelope(
        phase_metrics=phases,
        weights=_weights(),
        roundtrip_passenger_supported=True,
        actual_fractional_runtime=Decimal("0.8"),
    )
    assert env_half.complete_match_phase_count == 2
    assert env_point8.complete_match_phase_count == 2
    assert abs(
        env_point8.best_complete_phase_weighted_mean_gap_min
        - (env_half.best_complete_phase_weighted_mean_gap_min - 0.15)
    ) < 1e-9
    assert abs(
        env_point8.worst_complete_phase_weighted_mean_gap_min
        - (env_half.worst_complete_phase_weighted_mean_gap_min - 0.15)
    ) < 1e-9


def test_directional_only_route_ignores_vehicle_return_metrics():
    clean = _phase(999.0, 999.0, 4.0, 8.0)
    bad_vehicle = _phase(999.0, 999.0, 4.0, 8.0)
    bad_vehicle["vehicle_cycle_to_rail_milano_unmatched_count"] = 99
    bad_vehicle["vehicle_cycle_to_rail_lecco_unmatched_count"] = 99
    env = exact_weighted_phase_envelope(
        phase_metrics=[clean, bad_vehicle],
        weights=_weights(),
        roundtrip_passenger_supported=False,
        actual_fractional_runtime=Decimal("0.2"),
    )
    assert env.complete_match_phase_count == 2
    expected = (697.0 * 4.0 + 1185.0 * 8.0) / 1882.0
    assert abs(env.best_complete_phase_weighted_mean_gap_min - expected) < 1e-9
    assert abs(env.worst_complete_phase_weighted_mean_gap_min - expected) < 1e-9


def test_incomplete_required_cell_is_excluded_from_envelope():
    complete = _phase(10.0, 10.0, 5.0, 5.0)
    incomplete = _phase(1.0, 1.0, 1.0, 1.0)
    incomplete["rail_to_bus_lecco_unmatched_count"] = 1
    env = exact_weighted_phase_envelope(
        phase_metrics=[complete, incomplete],
        weights=_weights(),
        roundtrip_passenger_supported=True,
        actual_fractional_runtime=Decimal("0.5"),
    )
    assert env.evaluated_phase_count == 2
    assert env.complete_match_phase_count == 1
