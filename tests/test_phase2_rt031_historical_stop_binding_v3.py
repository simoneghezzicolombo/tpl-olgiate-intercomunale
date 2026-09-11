from src.phase2_rt031_historical_stop_binding_v3 import bind_historical_stops


def stop(target,native,family='FROZEN_GTFS_REFERENCE',kind='CONVENTIONAL_TPL'):
    return dict(stop_place_id=target,source_native_ids=native,source_families=family,service_class=kind)


def cross(sources,decision='SAME_STOP_PLACE_CONFIRMED'):
    return dict(crosswalk_id='X',target_source_records=sources,stop_place_decision=decision,boarding_point_decision='UNRESOLVED')


def test_provider_namespace_and_special_separation():
    got=bind_historical_stops([{'stop_id':'1'}],[stop('A','1','ASF_OPERATOR_OTP'),stop('S','1',kind='SPECIAL_SERVICE')],[])
    assert got['1']['frozen_stop_place_id'] is None


def test_exact_source_alias_does_not_merge_visits_or_boarding():
    got=bind_historical_stops([{'stop_id':'1'},{'stop_id':'L1'}],[stop('P','1|L1')],[])
    assert len(got)==2
    assert {r['frozen_stop_place_id'] for r in got.values()}=={'P'}
    assert all(r['directional_boarding_point_id'] is None for r in got.values())


def test_confirmed_crosswalk_preserves_coordinate_conflict():
    got=bind_historical_stops([{'stop_id':'old'}],[stop('FS','new')],[cross('FROZEN_GTFS::old|FROZEN_GTFS::new')])['old']
    assert got['frozen_stop_place_id']=='FS'
    assert got['status']=='CONFIRMED_CROSSWALK_STOP_PLACE'
    assert got['rt017_attachment_id'] is None and not got['source_coordinates_modified']


def test_strong_is_candidate_not_confirmed():
    got=bind_historical_stops([{'stop_id':'old'}],[stop('P','A','ASF_OPERATOR_OTP')],[cross('FROZEN_GTFS::old|ASF_OTP::A','SAME_STOP_PLACE_STRONG')])['old']
    assert got['candidate_stop_place_ids']==['P'] and got['frozen_stop_place_id'] is None


def test_conflicting_target_fails_closed():
    got=bind_historical_stops([{'stop_id':'old'}],[stop('P','old'),stop('Q','new')],[cross('FROZEN_GTFS::old|FROZEN_GTFS::new')])['old']
    assert got['status']=='AMBIGUOUS_STOP_PLACE' and got['frozen_stop_place_id'] is None
