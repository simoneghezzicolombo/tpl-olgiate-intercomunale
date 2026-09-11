"""Necessary kilometre-budget screen; no travel time or service feasibility inferred."""
from decimal import Decimal


def screen_cycle(distance_m, *, headway, start, end, days, cap_km):
    if any(type(x) is not int for x in (headway,start,end,days)) or headway<=0 or days<=0 or end<=start:
        raise ValueError('explicit integer headway/span/calendar required')
    distance,cap=Decimal(str(distance_m)),Decimal(str(cap_km))
    if not distance.is_finite() or distance<=0 or not cap.is_finite() or cap<=0:
        raise ValueError('positive finite distance and cap required')
    # Exact integer-minute phase enumeration, half-open departure window.
    counts=[len(range(start+phase,end,headway)) for phase in range(headway)]
    minimum,maximum=min(counts),max(counts)
    low=distance*minimum*days/1000
    high=distance*maximum*days/1000
    status=('REJECT_ALL_PHASES_DISTANCE_LOWER_BOUND' if low>cap else
            'DISTANCE_BOUND_WITHIN_CAP_ALL_PHASES' if high<=cap else
            'PHASE_DEPENDENT_DISTANCE_BOUND')
    return dict(status=status,minimum_daily_departures=minimum,maximum_daily_departures=maximum,
        phase_departure_counts=counts,minimum_annual_carrier_km=str(low),
        maximum_annual_carrier_km=str(high),
        maximum_cycle_distance_m_for_some_phase=None if minimum==0 else str(cap*1000/(minimum*days)),
        maximum_cycle_distance_m_for_every_phase=None if maximum==0 else str(cap*1000/(maximum*days)),
        operational_feasibility_certified=False,timetable_selected=False,
        depot_and_repositioning_cost_included=False)
