import json
from fractions import Fraction
from pathlib import Path

from scripts.phase2_compare_rt031_line8_santa_calco_exchange_v3 import dominates

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'


def test_current_baseline_reproduced_and_no_selected_point():
    result=json.loads((BASE/'santa_calco_exchange.json').read_text(encoding='utf-8'))
    baseline=json.loads((BASE/'conditional_proposal_17_trips.json').read_text(encoding='utf-8'))
    assert result['baseline_coverage_fraction']==baseline['coverage_fraction']
    assert result['new_calco_site_selected'] is False
    assert result['ready_for_rail_retiming'] is False
    assert result['bidirectional_h30_action_deferred'] is True
    assert result['primary_selection_authorised'] is False
    assert result['decision_budget_km'] is None


def test_street_corrections_and_centre_retained():
    result=json.loads((BASE/'santa_calco_exchange.json').read_text(encoding='utf-8'))
    assert result['piazza_san_zenone_retained'] is True
    assert set(result['street_exclusions_adopted_for_development'])=={'Via Mirasole','Via Cartiglio','Via Tessitura'}
    ids={e['stop_place_id'] for l in result['loops_without_new_calco_event'].values() for e in l['events']}
    assert 'FROZEN::300782' in ids
    assert 'ASF::SANTA_MARIA_HOE_VIA_COMO' not in ids
    assert len(ids)==25  # 26 sites including FS; one Calco point still to select.


def test_no_weights_and_every_frontier_member_nondominated():
    result=json.loads((BASE/'santa_calco_exchange.json').read_text(encoding='utf-8'))
    assert result['candidate_count']==len(result['candidates'])>0
    for row in result['candidates']:
        assert row['additional_road_distance_m']==0
        assert row['physical_boarding_authorised'] is False
        assert row['timetable_recalculated'] is False
        if row['candidate_id'] in result['unweighted_municipal_coverage_frontier_ids']:
            assert not any(dominates(other,row) for other in result['candidates'])
    assert all(Fraction(row['coverage_fraction']['97012']['5'])>
        Fraction(result['baseline_coverage_fraction']['97012']['5'])
        for row in result['candidates'] if row['candidate_id'] in result['unweighted_municipal_coverage_frontier_ids'])
