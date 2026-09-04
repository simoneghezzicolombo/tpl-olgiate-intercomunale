from src.phase2_exact_timetable_optimizer_v2 import (
    RouteInput, TransferProfile, best_continuous_quality_target, brute_force_oracle,
    choose_exact_phase_vector, clockface_times, exact_vehicle_blocks,
    precompute_route_phase_cells, rail_event_index, route_phase_cell_values,
    transfer_quality_from_slack,
)

P=(TransferProfile('P',2.0,4.0,1.5,12.0),)

def route(*, returns=True, public=20.0, cycle=20.0, rid='R'):
    return RouteInput(rid, public, cycle, True, returns, not returns, True, returns)

def rail():
    rows=[]
    for d in ('MILANO','LECCO'):
        for t in (300.0,330.0,360.0,390.0,420.0):
            rows.append({'direction':d,'arrival_min':t-1.0,'departure_min':t})
    return rail_event_index(rows)

def exhaustive_best(values, source, profile):
    scored=[]
    for target in values:
        slack=target-source-profile.transfer_walk_min
        q=transfer_quality_from_slack(slack, profile)
        scored.append((q,-abs(slack),-target,target))
    q,_,_,target=max(scored)
    return target,q

def test_clockface_start_inclusive_end_exclusive():
    assert clockface_times(0,30,300,391)==(300.0,330.0,360.0,390.0)
    assert clockface_times(15,30,300,391)==(315.0,345.0,375.0)

def test_transfer_quality_continuous_and_bounded():
    q0=transfer_quality_from_slack(0.0,P[0])
    q4=transfer_quality_from_slack(4.0,P[0])
    assert 0.0 < q0 < q4 <= 1.0

def test_best_quality_target_is_not_merely_first_next_event():
    matched=best_continuous_quality_target((102.0,106.0),100.0,P[0])
    assert matched is not None
    target,q=matched
    assert target==106.0
    assert q > transfer_quality_from_slack(0.0,P[0])

def test_localised_target_search_matches_full_all_target_scoring():
    profile=P[0]
    values=tuple(float(x) for x in range(75,176,7))
    for source in [80.0,81.5,99.0,100.0,103.25,149.0,180.0]:
        local=best_continuous_quality_target(values,source,profile)
        full=exhaustive_best(values,source,profile)
        assert local is not None
        assert local[0]==full[0]
        assert abs(local[1]-full[1]) < 1e-15

def test_open_route_has_no_bus_to_rail_cells():
    idx=rail()
    closed=route(returns=True)
    opened=route(returns=False)
    a=route_phase_cell_values(closed,phase=0,headway=30,span_start=300,span_end=421,rail_index=idx,profiles=P)
    b=route_phase_cell_values(opened,phase=0,headway=30,span_start=300,span_end=421,rail_index=idx,profiles=P)
    assert len(a)==4
    assert len(b)==2

def test_exact_solver_matches_independent_recursive_oracle_two_routes():
    idx=rail()
    routes=(route(rid='A',public=18,cycle=22), route(rid='B',public=27,cycle=31))
    pre=precompute_route_phase_cells(routes,headway=30,span_start=300,span_end=421,rail_index=idx,profiles=P)
    solved,n=choose_exact_phase_vector(30,pre)
    oracle,m=brute_force_oracle(30,pre)
    assert n==m==900
    assert solved.phase_vector==oracle.phase_vector
    assert solved.objective_key==oracle.objective_key

def test_lowest_phase_vector_is_final_tie_break():
    pre=(tuple((0.5,0.5) for _ in range(3)), tuple((0.5,0.5) for _ in range(3)))
    solved,n=choose_exact_phase_vector(3,pre)
    assert n==9
    assert solved.phase_vector==(0,0)

def test_exact_vehicle_blocks_interline_across_routes():
    routes=(route(rid='A',cycle=20),route(rid='B',cycle=20))
    fleet,assignment=exact_vehicle_blocks(routes,(0,15),headway=30,span_start=300,span_end=391,recovery_min=5)
    assert fleet==2
    assert len(assignment)==7
