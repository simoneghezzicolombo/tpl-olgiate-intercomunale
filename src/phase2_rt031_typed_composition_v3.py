"""Bounded RT-031 composition gate; not a territorial or service-search certificate.

No prefix merging, reversal, cycle rotation or implicit passenger continuity.
The finite route decomposition is supplied by the caller. Full edge history is
kept, so finite forbidden sequences can span arbitrarily many fragment borders.
Production RT-017/030 adapters and their completeness proofs remain separate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
from math import isfinite
from typing import Callable, Mapping


@dataclass(frozen=True)
class Edge:
    edge_id: str
    u: str
    v: str
    physical_id: str
    length_m: float
    epoch: str


@dataclass(frozen=True)
class StopEvent:
    event_id: str
    stop_id: str
    position: int  # node ordinal in this directed fragment, 0..len(edges)
    node_id: str
    pickup: bool | None
    dropoff: bool | None
    evidence_id: str
    service_role: str  # explicit, e.g. ORDINARY, TIMING, COMPULSORY_ALIGHT


@dataclass(frozen=True)
class Fragment:
    realization_id: str
    edge_ids: tuple[str, ...]
    events: tuple[StopEvent, ...]
    public_segments: tuple[bool | None, ...]
    # Passenger continuity at each INTERNAL node, distinct from vehicle motion.
    onboard_continuity: tuple[bool | None, ...]
    route_labels: tuple[str, ...]
    applicability: str
    epoch: str


@dataclass(frozen=True)
class Boundary:
    passenger_continuity: bool | None
    vehicle_continuity: bool | None
    evidence_id: str
    # Explicit matching of two records representing ONE physical/service event.
    same_event_pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RestrictionDomain:
    evidence_id: str
    epoch: str
    applicability: str
    complete: bool
    forbidden_sequences: tuple[tuple[str, ...], ...] = ()


def payload_hash(payload: object) -> str:
    """Label-preserving identity; deliberately no semantic/isomorphism dedup."""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _validate(fragment: Fragment, edges: Mapping[str, Edge]) -> None:
    n = len(fragment.edge_ids)
    if not n or not fragment.realization_id or not fragment.epoch or not fragment.applicability:
        raise ValueError("fragment requires identity, epoch, applicability and directed edges")
    if len(fragment.public_segments) != n or len(fragment.onboard_continuity) != n - 1:
        raise ValueError("segment/continuity dimensions do not match carrier")
    if any(x is not None and type(x) is not bool for x in
           (*fragment.public_segments, *fragment.onboard_continuity)):
        raise ValueError("service states must be boolean or explicit None")
    for eid in fragment.edge_ids:
        if eid not in edges:
            raise ValueError("unknown directed edge: " + eid)
        e = edges[eid]
        if e.edge_id != eid or not all((e.u, e.v, e.physical_id)):
            raise ValueError("invalid directed carrier identity")
        if e.epoch != fragment.epoch:
            raise ValueError("graph epoch mismatch")
        if not isfinite(e.length_m) or e.length_m <= 0:
            raise ValueError("carrier length must be finite and positive")
    nodes = [edges[fragment.edge_ids[0]].u] + [edges[e].v for e in fragment.edge_ids]
    if any(edges[a].v != edges[b].u for a, b in zip(fragment.edge_ids, fragment.edge_ids[1:])):
        raise ValueError("disconnected/reversed directed fragment")
    ids = [e.event_id for e in fragment.events]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate event identity within fragment")
    if [e.position for e in fragment.events] != sorted(e.position for e in fragment.events):
        raise ValueError("events must retain carrier order")
    for event in fragment.events:
        if (type(event.position) is not int or not 0 <= event.position <= n
                or nodes[event.position] != event.node_id):
            raise ValueError("stop occurrence is not on its directed carrier position")
        if not all((event.event_id, event.stop_id, event.evidence_id, event.service_role)):
            raise ValueError("missing stop occurrence provenance/service role")
        if any(x is not None and type(x) is not bool for x in (event.pickup, event.dropoff)):
            raise ValueError("pickup/dropoff must be boolean or explicit None")


def compose(
    fragments: tuple[Fragment, ...], boundaries: tuple[Boundary, ...],
    edges: Mapping[str, Edge], restrictions: RestrictionDomain,
    *, applicability: str,
    transition_oracle: Callable[[tuple[str, ...], str], bool | None] | None = None,
) -> dict:
    """Check a finite directed carrier and preserve linked service occurrences.

The optional oracle receives the ENTIRE prior carrier, not just its last edge.
None is UNKNOWN. A complete finite forbidden-sequence domain with no oracle
permits all contiguous transitions except those explicitly forbidden.
"""
    if not fragments or len(boundaries) != len(fragments) - 1:
        raise ValueError("explicit finite decomposition/boundaries required")
    if not restrictions.evidence_id or not restrictions.epoch or not applicability:
        raise ValueError("restriction provenance and operating context required")
    if type(restrictions.complete) is not bool:
        raise ValueError("restriction completeness must be explicit boolean")
    for rule in restrictions.forbidden_sequences:
        if not rule or any(e not in edges for e in rule):
            raise ValueError("invalid forbidden edge sequence")
    for f in fragments:
        _validate(f, edges)
        if f.epoch != restrictions.epoch:
            raise ValueError("restriction graph epoch mismatch")
    for b in boundaries:
        if not b.evidence_id or any(x is not None and type(x) is not bool for x in
                                  (b.passenger_continuity, b.vehicle_continuity)):
            raise ValueError("explicit typed boundary evidence required")
        if b.passenger_continuity is True and b.vehicle_continuity is not True:
            raise ValueError("onboard continuity requires explicit vehicle continuity")

    context_known = (restrictions.applicability == applicability
                     and all(f.applicability == applicability for f in fragments))
    unknown = not restrictions.complete or not context_known
    history: list[str] = []
    reasons: list[str] = []
    for f in fragments:
        for eid in f.edge_ids:
            if history and edges[history[-1]].v != edges[eid].u:
                reasons.append("DISCONNECTED_DIRECTED_CARRIER")
            candidate = tuple(history) + (eid,)
            if context_known and any(candidate[-len(rule):] == rule
                                     for rule in restrictions.forbidden_sequences):
                reasons.append("FORBIDDEN_HISTORY")
            if transition_oracle is not None and history and context_known:
                allowed = transition_oracle(tuple(history), eid)
                if allowed is not None and type(allowed) is not bool:
                    raise ValueError("transition oracle must return bool or None")
                unknown |= allowed is None
                if allowed is False:
                    reasons.append("FORBIDDEN_TRANSITION")
            history.append(eid)

    events: list[dict] = []
    segments: list[bool | None] = []
    continuity: list[bool | None] = []
    offset = 0
    for i, f in enumerate(fragments):
        incoming = [{**asdict(e), "position": e.position + offset,
                     "sources": [[i, f.realization_id, e.event_id, e.evidence_id]]}
                    for e in f.events]
        if i:
            b = boundaries[i - 1]
            continuity.append(b.passenger_continuity)
            left_ids, right_ids = set(), set()
            for left_id, right_id in b.same_event_pairs:
                if left_id in left_ids or right_id in right_ids:
                    raise ValueError("boundary correspondence must be one-to-one")
                left_ids.add(left_id)
                right_ids.add(right_id)
                left = [e for e in events if any(s[0] == i - 1 and s[2] == left_id for s in e["sources"])]
                right = [e for e in incoming if e["event_id"] == right_id]
                if len(left) != 1 or len(right) != 1:
                    raise ValueError("unknown boundary occurrence correspondence")
                a, z = left[0], right[0]
                keys = ("stop_id", "position", "node_id", "pickup", "dropoff", "service_role")
                if a["position"] != offset or any(a[k] != z[k] for k in keys):
                    raise ValueError("boundary records are not the same service visit")
                a["sources"].extend(z["sources"])
                incoming.remove(z)
        continuity.extend(f.onboard_continuity)
        segments.extend(f.public_segments)
        events.extend(incoming)
        offset += len(f.edge_ids)

    status = ("PROVEN_INFEASIBLE" if reasons else
              "UNKNOWN_EVIDENCE" if unknown else "CERTIFIED_FEASIBLE")
    linked = {"fragments": [asdict(f) for f in fragments],
              "boundaries": [asdict(b) for b in boundaries],
              "restrictions": asdict(restrictions), "applicability": applicability,
              "carrier": [asdict(edges[e]) for e in history], "events": events}
    def service_permission(permission, public):
        if permission is False or public is False:
            return False
        return True if permission is True and public is True else None

    effective = []
    for e in events:
        p = e["position"]
        effective.append((service_permission(e["pickup"], segments[p] if p < len(segments) else False),
                          service_permission(e["dropoff"], segments[p - 1] if p > 0 else False)))
    served = sorted({e["stop_id"] for e, permissions in zip(events, effective)
                     if True in permissions})
    identity_complete = all(True in permissions or permissions == (False, False)
                            for permissions in effective)
    journeys = []
    service_complete = (all(x is not None for x in (*segments, *continuity))
                        and all(e["pickup"] is not None and e["dropoff"] is not None for e in events))
    if status == "CERTIFIED_FEASIBLE":
        for i, a in enumerate(events):
            for j, b in enumerate(events):
                p, q = a["position"], b["position"]
                if (p < q and a["pickup"] is True and b["dropoff"] is True
                        and all(x is True for x in segments[p:q])
                        and all(x is True for x in continuity[p:q - 1])):
                    journeys.append([i, j])
    physical = {}
    for eid in history:
        e = edges[eid]
        if e.physical_id in physical and physical[e.physical_id] != e.length_m:
            raise ValueError("inconsistent length for one physical carrier")
        physical[e.physical_id] = e.length_m
    return {"status": status, "failure_reasons": sorted(set(reasons)),
            "payload": linked, "candidate_sha256": payload_hash(linked),
            "identity_stop_coverage": served, "identity_coverage_complete": identity_complete,
            "supported_onboard_event_pairs": journeys, "service_relations_complete": service_complete,
            "directed_pattern_traversal_length_m": sum(edges[e].length_m for e in history),
            "unique_physical_carrier_length_m": sum(physical.values()),
            "vehicle_run_distance_m": None, "territorial_certification": False}


def compose_domain(alternatives: tuple[tuple[Fragment, ...], ...], boundaries,
                   edges, restrictions, *, applicability: str,
                   alternatives_complete: bool, max_compositions: int,
                   transition_oracle=None) -> dict:
    """Lazy Cartesian traversal of a caller-declared FINITE realization domain.

Resource exhaustion/unknown evidence prevents exact quantifier claims. Identity
coverage is not a journey guarantee. No alternatives are interpreted as weights.
"""
    if not alternatives or type(max_compositions) is not int or max_compositions < 1:
        raise ValueError("finite nonempty decomposition and positive resource limit required")
    if type(alternatives_complete) is not bool:
        raise ValueError("alternative completeness must be explicit boolean")
    if len(boundaries) != len(alternatives) - 1:
        raise ValueError("boundary count differs from finite decomposition")
    for slot in alternatives:
        ids = [f.realization_id for f in slot]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate alternative identity")
    rows, exhausted = [], False
    for choice in product(*alternatives):
        if len(rows) == max_compositions:
            exhausted = True
            break
        rows.append(compose(choice, boundaries, edges, restrictions,
                            applicability=applicability, transition_oracle=transition_oracle))
    complete = alternatives_complete and not exhausted and all(r["status"] != "UNKNOWN_EVIDENCE" for r in rows)
    feasible = [r for r in rows if r["status"] == "CERTIFIED_FEASIBLE"]
    exact = complete and bool(feasible) and all(r["identity_coverage_complete"] for r in feasible)
    sets = [set(r["identity_stop_coverage"]) for r in feasible]
    return {"status": "RESOURCE_LIMIT_INCOMPLETE" if exhausted else
            "UNKNOWN_EVIDENCE" if not complete else
            "CERTIFIED_FEASIBLE" if feasible else "PROVEN_INFEASIBLE",
            "complete": complete, "checked_compositions": len(rows), "realizations": rows,
            "exact_identity_guarantees": exact,
            "guaranteed_stop_identities": sorted(set.intersection(*sets)) if exact else None,
            "possible_stop_identities": sorted(set.union(*sets)) if exact else None,
            "cross_realization_event_guarantees": None,
            "network_selected": False, "search_complete": False}
