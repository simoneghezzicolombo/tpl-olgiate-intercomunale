import hashlib
import json

import pytest

from scripts.phase2_close_rt031_fixed_order_runtime_audit_v3 import (
    OUTPUT,SHAPE,BRIEF,HELPER,SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR,STRENGTHENING,
    canonical_sha256,render_brief,
)
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import through_path


class Allow:
    def decision(self,history,next_edge):
        return {'allowed':True}


def edge(u,v,length,minutes):
    return dict(u_node_id=u,v_node_id=v,length_m=str(length),running_minutes_model=str(minutes))


@pytest.fixture(scope='module')
def result():
    return json.loads(OUTPUT.read_text(encoding='utf-8'))


def test_objective_changes_optimisation_not_physical_units():
    edges={'in':edge('a','b',1,.1),'short':edge('b','c',10,5),
        'long1':edge('b','d',20,.1),'long2':edge('d','c',20,.1),'out':edge('c','e',1,.1)}
    default=through_path(edges,Allow(),'in','out',[],set())
    fastest=through_path(edges,Allow(),'in','out',[],set(),objective='minutes')
    assert default['edge_ids']==['short'] and default['distance_m']==10 and default['running_minutes_model']==5
    assert fastest['edge_ids']==['long1','long2'] and fastest['distance_m']==40
    assert fastest['running_minutes_model']==pytest.approx(.2)
    with pytest.raises(ValueError,match='objective'):
        through_path(edges,Allow(),'in','out',[],set(),objective='weighted_score')


def test_time_search_retains_ordered_directional_memory():
    edges={'in':edge('a','b',1,.1),'bc':edge('b','c',1,.1),'cd':edge('c','d',1,.1),
        'dc':edge('d','c',1,.1),'db':edge('d','b',1,.1),'out':edge('b','e',1,.1)}
    answer=through_path(edges,Allow(),'in','out',[('c','bc'),('b','db')],set(),objective='minutes')
    assert answer['edge_ids']==['bc','cd','db']
    assert not through_path(edges,Allow(),'in','out',[('c','dc')],set(),objective='minutes')['reachable']


def test_sources_and_code_reproduce_pinned_scope(result):
    for path in (SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR,STRENGTHENING):
        assert result['source_canonical_sha256'][path.name]==canonical_sha256(json.loads(path.read_text(encoding='utf-8')))
    for path in (HELPER,HELPER.parent/'phase2_close_rt031_fixed_order_runtime_audit_v3.py'):
        assert result['generator_code_sha256'][path.name]==hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert BRIEF.read_text(encoding='utf-8')==render_brief(result)


def test_extreme_costs_are_not_a_claim_of_complete_pareto_or_global_optimisation(result):
    assert len(result['objective_extreme_cases'])==6
    assert len(result['distinct_path_witnesses'])==4
    assert result['relaxed_direction_domain_has_same_minimum_modeled_time']
    assert result['minimum_modeled_runtime_distance_change_m']==pytest.approx(41.6184250538)
    assert result['minimum_modeled_runtime_change_min']==pytest.approx(-.207805888777)
    assert result['internal_bounded_road_time_question_closed']
    assert not result['all_order_or_all_graph_optimality_claimed']
    assert not result['complete_pareto_frontier_claimed']
    assert not result['search_domain']['full_history_legal_domain_certified']
    strict=next(c for c in result['objective_extreme_cases'] if c['incoming_protection_policy']=='all_incoming' and c['objective']=='distance')
    design=json.loads(DESIGN.read_text(encoding='utf-8'))
    assert result['distinct_path_witnesses'][strict['witness_id']]['edge_ids']==design['loops']['east_A']['edge_ids']


def test_relaxed_occurrence_directions_are_not_silently_declared_preserved(result):
    for case in result['objective_extreme_cases']:
        assert case['all_14_ordered_service_nodes_preserved']
        assert case['all_directional_incoming_edges_preserved']==(case['incoming_protection_policy']!='node_only')
        witness=result['distinct_path_witnesses'][case['witness_id']]
        assert len(witness['ordered_service_events'])==14
        assert len({e['path_node_index'] for e in witness['ordered_service_events']})==14
        assert all(e['physical_boarding_authorised'] is False for e in witness['ordered_service_events'])


def test_optimistic_minimum_still_leaves_only_a_subminute_joint_phase_window(result):
    old=result['baseline_paired_flow_bound']['pairs'];new=result['minimum_runtime_paired_flow_bound']['pairs']
    assert len(old)==len(new)==5
    assert all(p['available_common_phase_interval_min']==pytest.approx(.2234063721) for p in old)
    assert all(p['available_common_phase_interval_min']==pytest.approx(.451992849756) for p in new)
    assert all(p['maximum_equal_residual_margin_by_retiming_only_min']==pytest.approx(.225996424878) for p in new)
    assert not result['minimum_runtime_paired_flow_bound']['normative_margin_selected']


def test_AM_minus2_is_a_complete_same_route_example_with_counterflow_cost(result):
    case=result['complete_AM_minus2_comparison']
    assert case['weekday_commercial_km']==pytest.approx(110334.947574727)
    assert case['maximum_conditional_vehicles']==4
    assert case['all_nine_event_ledgers_rebuilt_and_validated']
    assert len(case['all_27_complete_vehicle_blocks'])==27
    assert case['wing_train_rows_checked']==148 and case['transfer_flow_combinations_checked']==296
    assert case['additional_nominal_service_min_per_day_vs_confirmed']==pytest.approx(21.0058212431)
    assert case['additional_nominal_service_hours_2027_vs_confirmed']==pytest.approx(88.9246432624)
    waits=[(r['train_arrival_min'],r['old_rail_to_bus_wait_min'],r['new_rail_to_bus_wait_min'])
        for r in case['rail_flow_changes'] if r['wing']=='east_A' and r['train_arrival_min'] in (362,392,422,452,482)]
    assert waits==[(362,3,31),(392,3,31),(422,3,31),(452,3,31),(482,3,58)]
    assert case['lost_previous_all_nine_case_bus_to_rail']==[]
    assert case['comparison_not_adopted']


def test_time_proxy_savings_do_not_reduce_complete_trip_service_hours(result):
    case=result['complete_runtime_comparison']
    assert case['weekday_commercial_km']==pytest.approx(110504.084854146)
    # West departures are fixed: faster east moving time becomes extra FS
    # holding, not a free decrease of vehicle occupation or driver cost.
    assert case['additional_nominal_service_min_per_day_vs_confirmed']==pytest.approx(11.0058212431)
    assert case['lost_previous_all_nine_case_bus_to_rail']==[]
    assert not case['full_operating_cost_certified']


def test_phase_comparisons_have_no_implicit_AM_priority_or_selected_band(result):
    grid=result['fixed_geometry_AM_phase_comparisons_with_PM_plus2']
    assert [c['east_am_advance_min'] for c in grid]==list(range(5))
    assert all(c['event_readiness_and_complete_trip_checks_pass'] and c['maximum_model_vehicles']==4 for c in grid)
    for f in ('am_phase_change_adopted','runtime_route_change_adopted','normative_rail_priority_adopted',
              'actual_operator_implementation_ready','design_engineering_solidification_complete',
              'primary_selection_authorised','runner_up_selection_authorised','network_selected'):
        assert result[f] is False
    for f in ('decision_budget_km','uncertainty_band_min','missed_connection_probability','demand_weighted_gjt_improvement_min'):
        assert result[f] is None


def test_full_shapes_and_relocation_semantics_are_unambiguous():
    geo=json.loads(SHAPE.read_text(encoding='utf-8'))
    routes=[f for f in geo['features'] if f['properties'].get('role')=='FULL_ROUTE']
    assert len(routes)==4
    assert {(f['properties']['variant'],f['properties']['wing']) for f in routes}=={
        (v,w) for v in ('confirmed','runtime_and_scarpone_hypothesis') for w in ('east_A','west_B')}
    assert all(len(f['geometry']['coordinates'])>700 for f in routes)
    changed=[f for f in geo['features'] if f['properties'].get('role')=='CHANGED_SECTION']
    assert len(changed)==2
    hypothesis=[f for f in geo['features'] if f['properties'].get('role')=='HYPOTHETICAL_ATTACHMENT']
    assert len(hypothesis)==1 and not hypothesis[0]['properties']['adopted']
    assert len([f for f in geo['features'] if f['properties'].get('role')=='BASEMAP_ROAD'])>10
