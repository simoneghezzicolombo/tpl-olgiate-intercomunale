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


def closed_walk_metric_mst_bound(arcs, terminals):
    """Lower bound for ONE closed carrier walk visiting all mandatory terminals.

    Relax direction/turns, take shortest-path metric closure, then its MST.
    Shortcutting any admissible closed walk yields a metric tour; deleting one
    tour edge yields a terminal spanning tree. Thus MST <= closed-walk length.
    This does not bound disconnected service components operated independently.
    """
    import heapq
    graph={}
    for a,b,cost in arcs:
        w=Decimal(str(cost))
        if not w.is_finite() or w<=0:raise ValueError('positive finite arc cost required')
        graph.setdefault(a,{})[b]=min(w,graph.get(a,{}).get(b,w))
        graph.setdefault(b,{})[a]=min(w,graph.get(b,{}).get(a,w))
    terminals=sorted(set(terminals))
    if not terminals or any(t not in graph for t in terminals):raise ValueError('known nonempty terminals required')
    metric={}
    for source in terminals:
        distances={source:Decimal(0)}; queue=[(Decimal(0),source)]
        while queue:
            d,u=heapq.heappop(queue)
            if d!=distances[u]:continue
            for v,w in graph[u].items():
                if v not in distances or d+w<distances[v]:
                    distances[v]=d+w;heapq.heappush(queue,(d+w,v))
        if any(t not in distances for t in terminals):raise ValueError('disconnected mandatory terminals')
        metric[source]={t:distances[t] for t in terminals}
    used={terminals[0]};total=Decimal(0);witness=[]
    while len(used)<len(terminals):
        w,u,v=min((metric[u][v],u,v) for u in used for v in terminals if v not in used)
        used.add(v);total+=w;witness.append(dict(source=u,target=v,metric_distance_m=str(w)))
    return dict(lower_bound_m=str(total),mandatory_terminal_ids=terminals,
        metric_mst_edges=witness,scope='SINGLE_CLOSED_WALK_VISITING_ALL_MANDATORY_TERMINALS',
        directions_and_turn_restrictions_relaxed=True,route_order_assumed=False,
        feasibility_certified=False)
