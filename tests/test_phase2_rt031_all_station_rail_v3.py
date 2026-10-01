import copy
import pytest
from scripts.phase2_audit_rt031_all_station_rail_v3 import extract_all, parse_rfi, reconcile, train_number


def tables():
    return {'stops.txt':[{'stop_id':s,'stop_name':n} for s,n in [('S01514','Olgiate-Calco-Brivio'),('M','Milano Centrale'),('L','Lecco')]],
        'routes.txt':[{'route_id':'re','route_short_name':'RE8'}],
        'trips.txt':[{'trip_id':'a','route_id':'re','service_id':'x','trip_short_name':'2811'}],
        'calendar_dates.txt':[{'service_id':'x','date':'20261001','exception_type':'1'}],
        'stop_times.txt':[dict(trip_id='a',stop_id=s,stop_sequence=str(i),arrival_time=t,departure_time=t)
                          for i,(s,t) in enumerate([('L','23:30:00'),('S01514','24:03:00'),('M','24:40:00')],1)]}


def test_non_s8_call_and_midnight_remain_explicit():
    event=extract_all(tables(),'2026-10-01')[0]
    assert event['route_short_name']=='RE8'
    assert event['arrival_min']==1443 and event['direction']=='MILANO'
    assert event['origin_name']=='Lecco' and event['destination_name']=='Milano Centrale'
    assert reconcile([event],{'calls':[dict(train_number='2811',departure_clock_min=3)]})['matched']


def test_pass_through_without_station_call_not_counted():
    t=tables();t['stop_times.txt'][1]['stop_id']='L'
    with pytest.raises(ValueError,match='No station calls'): extract_all(t,'2026-10-01')


def test_repeated_station_and_duplicate_exceptions_fail_closed():
    t=tables();t['stop_times.txt'].append({**t['stop_times.txt'][1],'stop_sequence':'4'})
    with pytest.raises(ValueError,match='Ambiguous'): extract_all(t,'2026-10-01')
    t=tables();t['calendar_dates.txt']*=2
    with pytest.raises(ValueError,match='duplicate'): extract_all(t,'2026-10-01')


def test_pickup_restriction_and_platform_cluster():
    t=tables();t['stops.txt'].append(dict(stop_id='P',stop_name='Olgiate platform',parent_station='S01514'))
    t['stop_times.txt'][1].update(stop_id='P',pickup_type='1')
    e=extract_all(t,'2026-10-01')[0]
    assert e['station_stop_id']=='P' and not e['ordinary_boarding_supported']
    assert e['ordinary_alighting_supported']


def test_unknown_axis_not_fabricated_and_uncovered_date_fails():
    t=tables();t['stops.txt'][1]['stop_name']='Other terminal'
    assert extract_all(t,'2026-10-01')[0]['direction']=='UNKNOWN'
    with pytest.raises(ValueError,match='date unsupported'): extract_all(t,'2026-10-02')


def test_expired_rfi_not_relabelled_current():
    html=b'ORARIO PROGRAMMATO 14 Dicembre 2025 - 13 Giugno 2026 OLGIATE-CALCO-BRIVIO'
    with pytest.raises(ValueError,match='excludes'): parse_rfi(html,'2026-10-01')


def test_rfi_extra_train_blocks_reconciliation():
    event=extract_all(tables(),'2026-10-01')[0]
    cross=reconcile([event],{'calls':[dict(train_number='2811',departure_clock_min=3),dict(train_number='9',departure_clock_min=400)]})
    assert not cross['matched'] and cross['rfi_only']==[('9',400)]


def test_explicit_product_prefix_only_not_guessed_trip_number():
    assert train_number('S8 - 24817')=='24817'
    assert train_number('RE8 - 2811')=='2811'
    with pytest.raises(ValueError,match='Unsupported'): train_number('TN_2811_variant_02')
