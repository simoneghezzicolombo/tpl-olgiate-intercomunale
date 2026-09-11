"""Lossless RT-030 available-occurrence binding, including fractional positions.

This layer supplies carrier encounters, NOT public service events or legal route
composition. Source rows remain intact. No stop snapping, reversal, new eligibility,
boundary deduplication or service assignment is performed here.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from src.phase2_rt031_typed_composition_v3 import payload_hash

NODE = "CERTIFIED_ATTACHMENT_NODE_ON_ORDERED_PATH"
SEGMENT = "CERTIFIED_GLOBAL_NEAREST_PHYSICAL_SEGMENT_ON_ORDERED_PATH"


def decimal(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid carrier position/distance") from exc
    if not number.is_finite():
        raise ValueError("nonfinite carrier position/distance")
    return number


def unique(rows, key):
    result = {}
    for row in rows:
        value = row.get(key, "")
        if not value or value in result:
            raise ValueError("missing/duplicate " + key)
        result[value] = row
    return result


def bind_occurrences(patterns, occurrences, corridors, edges, stops, *, epoch):
    """Validate and bind a supplied corpus. Production hash gates live in runner."""
    pmap = unique(patterns, "realization_id")
    cmap = unique(corridors, "corridor_id")
    emap = unique(edges, "edge_id")
    smap = unique(stops, "stop_place_id")
    groups = defaultdict(list)
    for row in occurrences:
        if row["realization_id"] not in pmap:
            raise ValueError("unknown occurrence realization")
        groups[row["realization_id"]].append(row)
    if set(groups) != set(pmap):
        raise ValueError("missing realization occurrences")
    bound = {}
    for rid, pattern in sorted(pmap.items()):
        if pattern["graph_epoch_id"] != epoch:
            raise ValueError("pattern epoch mismatch")
        corridor = cmap[pattern["corridor_id"]]
        for field in ("pair_id", "graph_epoch_id", "path_geometry_sha256"):
            if corridor[field] != pattern[field]:
                raise ValueError("corridor/pattern identity mismatch: " + field)
        if corridor["elementary_for_structural_reduction"].lower() != "true":
            raise ValueError("non-elementary corridor")
        for pf, cf in (("source_endpoint_stop_id", "source_stop_place_id"),
                       ("target_endpoint_stop_id", "target_stop_place_id")):
            if pattern[pf] != corridor[cf]:
                raise ValueError("directional endpoint mismatch")
        edge_ids = corridor["path_edge_ids"].split(";")
        nodes = corridor["path_node_ids"].split(";")
        if len(nodes) != len(edge_ids) + 1 or not edge_ids:
            raise ValueError("carrier dimensions")
        digest = sha256(corridor["path_edge_ids"].encode()).hexdigest()
        if pattern["path_edge_ids_sha256"] != digest:
            raise ValueError("directed edge digest mismatch")
        cumulative = [Decimal(0)]
        carrier = []
        for i, eid in enumerate(edge_ids):
            e = emap[eid]
            if (e["u_node_id"], e["v_node_id"]) != (nodes[i], nodes[i + 1]):
                raise ValueError("directed edge/node mismatch")
            length = decimal(e["length_m"])
            if length <= 0:
                raise ValueError("nonpositive carrier length")
            cumulative.append(cumulative[-1] + length)
            carrier.append({"ordinal": i, "source_edge": dict(e)})
        rows = sorted(groups[rid], key=lambda r: decimal(r["stop_sequence"]))
        if [decimal(r["stop_sequence"]) for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError("occurrence sequence gap/duplicate")
        if [decimal(r["ordinal_position"]) for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError("occurrence ordinal mismatch")
        if ";".join(r["stop_place_id"] for r in rows) != pattern["ordered_passenger_stop_ids"]:
            raise ValueError("pattern occurrence order mismatch")
        if decimal(pattern["passenger_stop_count"]) != len(rows):
            raise ValueError("pattern occurrence count mismatch")
        visits, previous = [], Decimal(-1)
        for row in rows:
            for field in ("structural_link_id", "direction", "pair_id", "corridor_id",
                          "graph_epoch_id", "path_geometry_sha256", "path_edge_ids_sha256"):
                if row[field] != pattern[field]:
                    raise ValueError("occurrence lineage mismatch: " + field)
            stop = smap[row["stop_place_id"]]
            if (stop["graph_epoch_id"] != epoch or stop["service_class"] != "CONVENTIONAL_TPL"
                    or stop["automatic_materialization_eligible"].lower() != "true"):
                raise ValueError("stop eligibility/epoch mismatch")
            if stop["graph_node_id"] != row["certified_attachment_node_id"]:
                raise ValueError("attachment node lineage mismatch")
            if decimal(row["route_proximity_buffer_m"]) != 0:
                raise ValueError("route proximity buffer forbidden")
            pos = decimal(row["path_position"])
            if not previous <= pos <= len(edge_ids) or pos < 0:
                raise ValueError("invalid/reordered carrier position")
            previous = pos
            binding = {"position": str(pos), "node_id": None, "edge_id": None,
                       "edge_ordinal": None, "fraction": None}
            if row["evidence_type"] == NODE:
                if pos != int(pos) or row["path_node_id"] != nodes[int(pos)] or row["path_edge_id"]:
                    raise ValueError("node occurrence carrier mismatch")
                if row["path_node_id"] != stop["graph_node_id"]:
                    raise ValueError("node attachment not encountered")
                binding["node_id"] = nodes[int(pos)]
                expected_distance = cumulative[int(pos)]
                tolerance = Decimal("0.000001")
            elif row["evidence_type"] == SEGMENT:
                # Rounded fractional positions may equal an edge endpoint. Keep
                # explicit edge evidence, never snap to the nearest node.
                options = [i for i in {int(pos), int(pos) - 1}
                           if 0 <= i < len(edge_ids) and i <= pos <= i + 1
                           and edge_ids[i] == row["path_edge_id"]]
                if len(options) != 1 or row["path_node_id"]:
                    raise ValueError("segment occurrence carrier mismatch/ambiguity")
                i = options[0]
                endpoints = sorted((nodes[i], nodes[i + 1]))
                physical = "RT030_SEG_" + sha256("|".join(endpoints).encode()).hexdigest()[:20].upper()
                if row["global_nearest_physical_segment_id"] != physical:
                    raise ValueError("physical segment lineage mismatch")
                fraction = pos - i
                binding.update(edge_id=edge_ids[i], edge_ordinal=i, fraction=str(fraction))
                length = cumulative[i + 1] - cumulative[i]
                expected_distance = cumulative[i] + fraction * length
                # RT-030 serializes position and distance to nine decimals.
                tolerance = Decimal("0.000001") + length * Decimal("0.000000001")
            else:
                raise ValueError("unsupported attachment evidence")
            if abs(decimal(row["distance_from_path_start_m"]) - expected_distance) > tolerance:
                raise ValueError("occurrence distance/position mismatch")
            visits.append({"binding": binding, "source_occurrence": dict(row),
                           "source_stop": dict(stop), "availability_only": True,
                           "pickup": None, "dropoff": None, "public_service": None})
        payload = {"realization_id": rid, "source_pattern": dict(pattern),
                   "source_corridor": dict(corridor), "carrier": carrier, "visits": visits,
                   "graph_epoch": epoch, "turn_composition_status": "UNKNOWN_EVIDENCE",
                   "service_assignment_status": "UNASSIGNED"}
        bound[rid] = {"payload": payload, "sha256": payload_hash(payload)}
    return bound


def concatenate_available(bound, realization_ids):
    """Finite caller-supplied carrier chain; preserves every source visit/revisit.

Contiguity is checked, but never promoted to turn legality or passenger service.
"""
    if not realization_ids:
        raise ValueError("empty carrier chain")
    edges, visits, epochs, prior_node = [], [], set(), None
    for slot, rid in enumerate(realization_ids):
        item = bound[rid]["payload"]
        epochs.add(item["graph_epoch"])
        if len(epochs) != 1:
            raise ValueError("mixed graph epochs")
        source_edges = item["carrier"]
        if prior_node is not None and prior_node != source_edges[0]["source_edge"]["u_node_id"]:
            raise ValueError("disconnected carrier chain")
        offset = len(edges)
        edges.extend({"slot": slot, "source_realization": rid, **e} for e in source_edges)
        for visit in item["visits"]:
            visits.append({"slot": slot, "source_realization": rid,
                           "composed_position": str(decimal(visit["binding"]["position"]) + offset),
                           "source_visit": visit})
        prior_node = source_edges[-1]["source_edge"]["v_node_id"]
    payload = {"realization_ids": list(realization_ids), "carrier": edges, "visits": visits,
               "turn_composition_status": "UNKNOWN_EVIDENCE", "service_assignment_status": "UNASSIGNED",
               "boundary_occurrences_merged": False, "passenger_guarantees": None}
    return {"payload": payload, "sha256": payload_hash(payload)}
