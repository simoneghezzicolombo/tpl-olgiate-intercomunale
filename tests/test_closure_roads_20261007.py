import pytest

from scripts.phase2_closure_roads_20261007 import exclusion_proof


def test_absent_via_only_excludes_internal_pattern_not_unknown_inherited_history():
    relation = dict(relation_id='r', restriction='no_left_turn',
                    from_way_ids=['10'], via_way_ids=['20'], to_way_ids=['30'])
    proof = exclusion_proof(['osm:10:0:F', 'osm:30:0:F'], [relation])[0]
    assert proof['internal_and_cyclic_pattern_excluded'] is True
    assert proof['inapplicability_proved'] is False


def test_present_via_way_does_not_claim_illegality_or_inapplicability():
    relation = dict(relation_id='r', restriction='no_left_turn', via_way_ids=['20'])
    proof = exclusion_proof(['osm:20:0:F'], [relation])[0]
    assert proof['inapplicability_proved'] is False
    assert proof['complete_route_overlap'] == ['20']


def test_missing_via_members_rejected():
    with pytest.raises(ValueError):
        exclusion_proof([], [dict(relation_id='r', via_way_ids=[])])


def test_active_incoming_prefix_forbids_first_to_edge_despite_absent_via():
    relation = dict(relation_id='r', restriction='no_left_turn',
                    from_way_ids=['10'], via_way_ids=['20'], to_way_ids=['30'])
    proof = exclusion_proof(['osm:30:0:F'], [relation], ['r'])[0]
    assert proof['internal_and_cyclic_pattern_excluded'] is True
    assert proof['supplied_active_prefix_forbids_first_target'] is True
    assert proof['inapplicability_proved'] is False


def test_absent_no_target_excludes_internal_cyclic_and_inherited_effects():
    relation = dict(relation_id='r', restriction='no_left_turn',
                    from_way_ids=['10'], via_way_ids=['20'], to_way_ids=['30'])
    proof = exclusion_proof(['osm:99:0:F'], [relation], ['r'])[0]
    assert proof['unknown_initial_history_excluded'] is True
    assert proof['inapplicability_proved'] is True
    assert proof['supplied_active_prefix_forbids_first_target'] is False
