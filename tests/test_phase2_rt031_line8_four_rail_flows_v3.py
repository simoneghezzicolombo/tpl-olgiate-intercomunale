from scripts.phase2_audit_rt031_line8_four_rail_flows_v3 import onward_bus, build


def test_transfer_walk_and_long_wait_not_relabelled_useful():
    row=onward_bus(992,[990,993,1020])
    assert row['bus_departure_min']==1020
    assert row['total_wait_from_train_arrival_min']==28
    assert row['meets_inherited_3_to_8_min_window'] is False


def test_missing_next_bus_is_not_zero_wait():
    assert onward_bus(1200,[1180])['total_wait_from_train_arrival_min'] is None


def test_all_four_flows_and_frozen_semantics():
    result=build()
    assert len(result['rows'])==148
    assert {r['train_direction'] for r in result['rows']}=={'MILANO','LECCO'}
    assert all('rail_to_bus' in r and 'bus_to_rail' in r for r in result['rows'])
    for row in result['rows']:
        assert row['train_origin_city']!=row['train_direction']
    row=next(r for r in result['rows'] if r['wing']=='west_B'
             and r['train_origin_city']=='LECCO' and r['train_arrival_min']==1015)
    assert row['rail_to_bus']['total_wait_from_train_arrival_min']==5
    assert result['network_selected'] is False
    assert result['current_rail_timetable_verified'] is False
    assert result['street_revisions_retimed'] is False
