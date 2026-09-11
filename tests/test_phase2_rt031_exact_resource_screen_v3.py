from decimal import Decimal
import pytest
from src.phase2_rt031_exact_resource_screen_v3 import screen_cycle


def test_rt001_partial_last_interval_is_phase_dependent():
    r=screen_cycle(1000,headway=20,start=330,end=1440,days=1,cap_km=55)
    assert (r['minimum_daily_departures'],r['maximum_daily_departures'])==(55,56)
    assert r['status']=='PHASE_DEPENDENT_DISTANCE_BOUND'


def test_exact_budget_equality_is_not_rejected():
    r=screen_cycle('26783.41346153846153846153846',headway=60,start=360,end=1320,days=260,cap_km=111419)
    assert Decimal(r['maximum_annual_carrier_km'])<=111419
    assert not r['operational_feasibility_certified']


def test_shortest_declared_stress_cycle_exceeds_even_hourly_budget():
    r=screen_cycle(35139,headway=60,start=360,end=1320,days=260,cap_km=111419)
    assert r['status']=='REJECT_ALL_PHASES_DISTANCE_LOWER_BOUND'
    assert r['minimum_annual_carrier_km']=='146178.24'


def test_half_open_window_omits_departure_at_end():
    r=screen_cycle(1000,headway=30,start=360,end=420,days=1,cap_km=2)
    assert set(r['phase_departure_counts'])=={2}


@pytest.mark.parametrize('value',[0,-1,'NaN','Infinity'])
def test_invalid_distance(value):
    with pytest.raises(ValueError):screen_cycle(value,headway=30,start=0,end=60,days=1,cap_km=10)
