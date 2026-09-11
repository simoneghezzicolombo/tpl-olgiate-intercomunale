"""Pairwise RT-023 physical compatibility graph and exact slot-sequence DP.

This optimization is valid only when transition history locality is certified for
the declared carrier domain. For the frozen RT-023 domain that will require a
separate proof that successor-envelope via-way restrictions are irrelevant. Under
that condition, every multi-atom transition is either internal to one certified
atomic carrier or exactly one boundary between the left atom's final directed edge
and the right atom's first directed edge. Frozen represented via-node semantics
are therefore pairwise-compositional.

No service, passenger continuity or route-pattern semantics are inferred here.
"""
from __future__ import annotations

from collections import defaultdict

LEGAL = "CERTIFIED_PAIRWISE_PHYSICAL_COMPATIBLE"
ILLEGAL = "PROVEN_PAIRWISE_PHYSICAL_INCOMPATIBLE"
UNKNOWN = "UNKNOWN_PAIRWISE_PHYSICAL_COMPATIBILITY"


def build_pairwise_compatibility(
    catalog,
    boundary_rows,
    transition_oracle,
    *,
    history_locality_certified: bool,
):
    if type(history_locality_certified) is not bool:
        raise ValueError("history locality certification must be explicit")
    boundary = {}
    for raw in boundary_rows:
        row = dict(raw)
        key = (str(row.get("left_realization_id", "")), str(row.get("right_realization_id", "")))
        if not all(key) or key in boundary:
            raise ValueError("invalid/duplicate boundary row")
        boundary[key] = row

    rows = []
    ids = sorted(catalog)
    for left_id in ids:
        left = catalog[left_id]
        for right_id in ids:
            if left_id == right_id:
                continue
            right = catalog[right_id]
            if left["target_stop_id"] != right["source_stop_id"]:
                continue
            reasons = []
            unknown = False
            b = boundary.get((left_id, right_id))
            if left["target_graph_node_id"] != right["source_graph_node_id"]:
                reasons.append("BOUNDARY_GRAPH_NODE_DISCONTINUITY")
            if b is None:
                unknown = True
            elif str(b.get("boundary_location_status", "")) != "CERTIFIED_SAME_BOUNDARY_LOCATION":
                unknown = True

            # Full left-atom history is supplied. A pairwise-positive result is
            # nevertheless authorized only if higher-order history relevance has
            # been separately certified absent for this scope.
            decision = transition_oracle(tuple(left["edge_ids"]), right["edge_ids"][0])
            if decision is False:
                reasons.append("FORBIDDEN_BOUNDARY_TRANSITION")
            elif decision is None:
                unknown = True
            elif type(decision) is not bool:
                raise ValueError("transition oracle must return bool or None")
            if decision is True and not history_locality_certified:
                unknown = True

            status = ILLEGAL if reasons else UNKNOWN if unknown else LEGAL
            rows.append({
                "left_realization_id": left_id,
                "right_realization_id": right_id,
                "boundary_stop_id": left["target_stop_id"],
                "status": status,
                "failure_reasons": tuple(sorted(set(reasons))),
                "boundary_correspondence_id": None if b is None else b.get("boundary_correspondence_id"),
                "service_semantics_assigned": False,
                "passenger_continuity_inferred": False,
                "vehicle_continuity_inferred": False,
            })
    return rows


def exact_slot_sequence_count(ordered_slots, by_slot, pairwise_rows):
    """Count compatible realization sequences without enumerating their product.

    Exactness fails closed if any relevant adjacent alternative pair is UNKNOWN or
    absent from the supplied pairwise catalog. ILLEGAL pairs are known-zero arcs.
    """
    if not ordered_slots:
        raise ValueError("nonempty ordered slot decomposition required")
    slots = []
    for raw in ordered_slots:
        if len(raw) != 2:
            raise ValueError("slot must contain structural link and direction")
        slot = (str(raw[0]), str(raw[1]))
        if slot not in by_slot or not by_slot[slot]:
            raise ValueError("slot has no certified alternatives")
        slots.append(slot)

    pair_index = {}
    for row in pairwise_rows:
        key = (str(row["left_realization_id"]), str(row["right_realization_id"]))
        if key in pair_index:
            raise ValueError("duplicate pairwise compatibility record")
        pair_index[key] = row

    # One single atom needs no inter-fragment transition.
    counts = {r["realization_id"]: 1 for r in by_slot[slots[0]]}
    reachable_by_slot = [tuple(sorted(counts))]
    exact = True
    unknown_relevant_pairs = []

    for slot_index, slot in enumerate(slots[1:], start=1):
        next_counts = defaultdict(int)
        for left_id, left_count in sorted(counts.items()):
            if left_count == 0:
                continue
            for right in by_slot[slot]:
                right_id = right["realization_id"]
                row = pair_index.get((left_id, right_id))
                if row is None:
                    exact = False
                    unknown_relevant_pairs.append([left_id, right_id, "MISSING_PAIRWISE_RECORD"])
                    continue
                if row["status"] == LEGAL:
                    next_counts[right_id] += left_count
                elif row["status"] == ILLEGAL:
                    continue
                elif row["status"] == UNKNOWN:
                    exact = False
                    unknown_relevant_pairs.append([left_id, right_id, "UNKNOWN_PAIRWISE_STATUS"])
                else:
                    raise ValueError("invalid pairwise compatibility status")
        counts = dict(next_counts)
        reachable_by_slot.append(tuple(sorted(counts)))

    count = sum(counts.values()) if exact else None
    return {
        "status": "CERTIFIED_EXACT_COMPATIBLE_SEQUENCE_COUNT" if exact else "UNKNOWN_COMPATIBLE_SEQUENCE_COUNT",
        "exact": exact,
        "ordered_slots": [list(s) for s in slots],
        "compatible_sequence_count": count,
        "compatible_sequence_exists": (count > 0) if exact else None,
        "reachable_realization_ids_by_slot": [list(v) for v in reachable_by_slot],
        "unknown_relevant_pairs": unknown_relevant_pairs,
        "cartesian_product_not_materialized": True,
        "service_semantics_assigned": False,
        "network_selected": False,
    }
