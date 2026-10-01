import json
from pathlib import Path

import pytest

from scripts.phase2_audit_rt031_line8_caller_streets_v3 import excluded_ways

ROOT=Path(__file__).resolve().parents[1]


def test_exact_street_names_only():
    elements=[{'type':'way','id':1,'tags':{'name':'Via Mirasole'}},
        {'type':'way','id':2,'tags':{'name':'Via Mirasoletta'}},
        {'type':'node','id':3,'tags':{'name':'Via Mirasole'}}]
    assert excluded_ways(elements,['Via Mirasole'])=={'1'}


def test_missing_street_fails_closed():
    with pytest.raises(ValueError,match='not completely resolved'):
        excluded_ways([],['Via Mirasole'])


def test_caller_revision_does_not_select_or_invent_preferences():
    authority=json.loads((ROOT/'config/rt031_caller_street_and_rail_revision_v3.json').read_text())
    for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised'):
        assert authority[flag] is False
    assert authority['decision_budget_km'] is None
    assert authority['uncertainty_band_min'] is None
    assert authority['rail_audit']['required_directions']==['MILANO','LECCO']
    assert authority['rail_audit']['required_interchanges']==['BUS_TO_RAIL','RAIL_TO_BUS']
    assert authority['bidirectional_peak_service']['baseline_provides_this'] is False
    assert authority['fs_holding']['numeric_maximum_declared'] is None


def test_generated_paths_exclude_resolved_ways_and_keep_local_occurrences():
    output=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3/caller_street_exclusions.json'
    audit=json.loads(output.read_text(encoding='utf-8'))
    assert len(audit['cases'])==7
    for case in audit['cases']:
        assert case['retimed'] is False
        assert case['bus_suitability_certified'] is False
        assert case['annual_service_km_certified'] is False
        if not case['reachable_with_same_ordered_events_and_boundaries']:
            continue
        assert case['site_count_including_fs']==27
        for wing,loop in case['loops'].items():
            assert not set(e.split(':')[1] for e in loop['edge_ids']) & set(case['excluded_osm_way_ids'])
            local='PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE' if wing=='east_A' else 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'
            occurrences=[e['path_node_index'] for e in loop['events'] if e['stop_place_id']==local]
            assert len(occurrences)==2 and occurrences[0]<occurrences[1]
