from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_d_pass_analysis import (
    add_composite,
    budget_envelope,
    build_directional_pairs,
    fleet_headway_envelope,
    load_compact_pass_snapshot,
)
from src.service_math import ServiceMathError

METRICS = ROOT / 'data/processed/gate_d_pass/structural_candidate_metrics.csv'
LOOPS = ROOT / 'data/processed/gate_d_pass/candidate_loop_evidence.csv'
METRICS_SHA = '0d2c187b888ce711da04fb96a8ff8f6e638f67980099e9d9e67a073b9b6cc2a1'
LOOPS_SHA = 'b12a047efc70f8cf816cd905a9a6de56ebfee200b1815295f42f75d2b9fbbf4e'
SOURCE_WAYPOINTS_SHA = 'a8bf8fe133590230b4cd063b58c3332d27243c11b501c160979a2e1a94de054b'


def get_pairs():
    metrics, waypoints = load_compact_pass_snapshot(
        METRICS, LOOPS, METRICS_SHA, LOOPS_SHA, SOURCE_WAYPOINTS_SHA
    )
    return build_directional_pairs(metrics, waypoints)


def test_exact_pass_snapshot_hash_and_pairing():
    pairs, unpaired = get_pairs()
    assert {r['route_id'] for r in pairs} == {
        'WEST_COMPACT_MONDONICO',
        'EAST_COMPACT_ARLATE',
        'EAST_CALCO_SUPERIORE_SENSITIVITY',
    }
    assert len(unpaired) == 5


def test_wrong_snapshot_hash_fails_closed():
    with pytest.raises(ServiceMathError, match='metrics snapshot SHA256 mismatch'):
        load_compact_pass_snapshot(METRICS, LOOPS, '0' * 64, LOOPS_SHA, SOURCE_WAYPOINTS_SHA)


def test_compact_figure8_composition_is_assumption_and_exact_math():
    pairs, _ = get_pairs()
    f = add_composite(pairs, 'FIG8_COMPACT', ['WEST_COMPACT_MONDONICO', 'EAST_COMPACT_ARLATE'])
    assert f['route_definition_status'] == 'ASSUMPTION'
    assert f['route_km_CW'] == pytest.approx(23.706064471922054)
    assert f['route_km_CCW'] == pytest.approx(23.037668051219607)
    assert f['pure_running_min_CW'] == pytest.approx(45.77727858152314)
    assert f['pure_running_min_CCW'] == pytest.approx(44.95515723328815)


def test_figure8_budget_integer_boundary_is_2383_not_false_zero():
    pairs, _ = get_pairs()
    f = add_composite(pairs, 'FIG8_COMPACT', ['WEST_COMPACT_MONDONICO', 'EAST_COMPACT_ARLATE'])
    r = budget_envelope([f], 111419.0, {'gate_d_status': 'PASS'})[0]
    assert r['max_equal_CW_CCW_cycles_year_under_budget'] == 2383
    assert r['annual_bus_km_at_max_equal_pairs'] == pytest.approx(111390.31460264657)
    assert r['budget_margin_km_at_max_equal_pairs'] == pytest.approx(28.68539735343)
    assert r['next_equal_pair_delta_km_vs_budget'] == pytest.approx(18.05833516971)
    assert r['budget_margin_km_at_max_equal_pairs'] != 0


def test_figure8_60min_one_vehicle_each_direction_allowance():
    pairs, _ = get_pairs()
    f = add_composite(pairs, 'FIG8_COMPACT', ['WEST_COMPACT_MONDONICO', 'EAST_COMPACT_ARLATE'])
    rows = fleet_headway_envelope([f], [60], [1], {'gate_d_status': 'PASS'})
    by = {r['direction']: r for r in rows}
    assert by['CW']['maximum_dwell_plus_recovery_min_compatible'] == pytest.approx(14.22272141847686)
    assert by['CCW']['maximum_dwell_plus_recovery_min_compatible'] == pytest.approx(15.04484276671185)
    assert by['CW']['combined_rate_equivalent_at_common_stops_if_symmetric_min'] == 30


def test_figure8_45min_one_vehicle_cw_impossible_even_before_dwell():
    pairs, _ = get_pairs()
    f = add_composite(pairs, 'FIG8_COMPACT', ['WEST_COMPACT_MONDONICO', 'EAST_COMPACT_ARLATE'])
    rows = fleet_headway_envelope([f], [45], [1], {})
    by = {r['direction']: r for r in rows}
    assert by['CW']['headway_possible_with_zero_nonrunning'] is False
    assert by['CCW']['maximum_dwell_plus_recovery_min_compatible'] < 0.05


def test_unpaired_extensions_never_become_bidirectional_service_scenarios():
    _, unpaired = get_pairs()
    ids = {r['candidate_id'] for r in unpaired}
    assert {'WEST_RAVELLINO_EXTENSION', 'EAST_CAPRINO_CELANA_EXTENSION', 'WEST_SAN_ZENO_SENSITIVITY'} <= ids
    assert all(r['gate_e_pairing_status'].startswith('UNPAIRED') for r in unpaired)
