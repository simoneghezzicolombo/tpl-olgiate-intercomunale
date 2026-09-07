"""RT-031 boundary-location correspondence over certified atomic realizations.

This layer proves only that two carrier-contiguous atomic realizations meet at the
same certified passenger-stop boundary location. It does NOT infer that they are
one vehicle run, one service event, passenger-through continuity, pickup/dropoff,
or that boundary occurrences may be merged.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Iterable, Mapping

NODE_EVIDENCE = "CERTIFIED_ATTACHMENT_NODE_ON_ORDERED_PATH"
CERTIFIED = "CERTIFIED_SAME_BOUNDARY_LOCATION"
UNKNOWN = "UNKNOWN_BOUNDARY_LOCATION"


def _unique(rows: Iterable[Mapping], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        value = str(row.get(key, ""))
        if not value or value in out:
            raise ValueError(f"missing/duplicate {key}")
        out[value] = row
    return out


def _seq(value) -> int:
    number = float(value)
    if not number.is_integer() or number < 1:
        raise ValueError("invalid positive occurrence sequence")
    return int(number)


def build_boundary_catalog(patterns, occurrences, corridors, edges):
    pmap = _unique(patterns, "realization_id")
    cmap = _unique(corridors, "corridor_id")
    emap = _unique(edges, "edge_id")

    groups: dict[str, list[dict]] = defaultdict(list)
    for raw in occurrences:
        row = dict(raw)
        rid = str(row.get("realization_id", ""))
        if rid not in pmap:
            raise ValueError("occurrence references unknown realization")
        groups[rid].append(row)
    if set(groups) != set(pmap):
        raise ValueError("missing occurrence group for realization")

    realization = {}
    for rid, pattern in sorted(pmap.items()):
        corridor_id = str(pattern.get("corridor_id", ""))
        if corridor_id not in cmap:
            raise ValueError("pattern references unknown corridor")
        corridor = cmap[corridor_id]
        if str(corridor.get("elementary_for_structural_reduction", "")).lower() != "true":
            raise ValueError("non-elementary corridor in boundary catalog")
        edge_ids = str(corridor.get("path_edge_ids", "")).split(";")
        edge_ids = [e for e in edge_ids if e]
        node_ids = str(corridor.get("path_node_ids", "")).split(";")
        if not edge_ids or len(node_ids) != len(edge_ids) + 1:
            raise ValueError("invalid corridor carrier dimensions")
        for eid in edge_ids:
            if eid not in emap:
                raise ValueError("corridor references unknown edge")
        for left, right in zip(edge_ids[:-1], edge_ids[1:]):
            if str(emap[left]["v_node_id"]) != str(emap[right]["u_node_id"]):
                raise ValueError("non-contiguous atomic carrier")

        rows = sorted(groups[rid], key=lambda r: _seq(r.get("stop_sequence")))
        if [_seq(r.get("stop_sequence")) for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError("occurrence sequence gap/duplicate")
        first, last = rows[0], rows[-1]
        source_stop = str(pattern.get("source_endpoint_stop_id", ""))
        target_stop = str(pattern.get("target_endpoint_stop_id", ""))
        if str(first.get("stop_place_id", "")) != source_stop:
            raise ValueError("first occurrence is not source endpoint")
        if str(last.get("stop_place_id", "")) != target_stop:
            raise ValueError("last occurrence is not target endpoint")
        if str(first.get("path_node_id", "")) != str(emap[edge_ids[0]]["u_node_id"]):
            raise ValueError("source endpoint occurrence not at carrier start node")
        if str(last.get("path_node_id", "")) != str(emap[edge_ids[-1]]["v_node_id"]):
            raise ValueError("target endpoint occurrence not at carrier end node")
        realization[rid] = {
            "pattern": pattern,
            "first_edge": edge_ids[0],
            "last_edge": edge_ids[-1],
            "first_occurrence": first,
            "last_occurrence": last,
        }

    catalog = []
    ids = sorted(realization)
    for left_id in ids:
        left = realization[left_id]
        left_edge = emap[left["last_edge"]]
        for right_id in ids:
            if left_id == right_id:
                continue
            right = realization[right_id]
            right_edge = emap[right["first_edge"]]
            if str(left_edge["v_node_id"]) != str(right_edge["u_node_id"]):
                continue

            left_stop = str(left["pattern"]["target_endpoint_stop_id"])
            right_stop = str(right["pattern"]["source_endpoint_stop_id"])
            if left_stop != right_stop:
                raise ValueError("carrier-contiguous realizations disagree on boundary stop")

            lo = left["last_occurrence"]
            ro = right["first_occurrence"]
            boundary_node = str(left_edge["v_node_id"])
            same_node_evidence = (
                str(lo.get("evidence_type", "")) == NODE_EVIDENCE
                and str(ro.get("evidence_type", "")) == NODE_EVIDENCE
                and str(lo.get("stop_place_id", "")) == left_stop
                and str(ro.get("stop_place_id", "")) == left_stop
                and str(lo.get("certified_attachment_node_id", "")) == boundary_node
                and str(ro.get("certified_attachment_node_id", "")) == boundary_node
                and str(lo.get("path_node_id", "")) == boundary_node
                and str(ro.get("path_node_id", "")) == boundary_node
            )
            status = CERTIFIED if same_node_evidence else UNKNOWN
            evidence_key = "|".join([
                left_id,
                str(lo.get("stop_sequence", "")),
                right_id,
                str(ro.get("stop_sequence", "")),
                left_stop,
                boundary_node,
            ])
            catalog.append({
                "boundary_correspondence_id": "RT031_BOUNDARY_" + sha256(evidence_key.encode()).hexdigest()[:20].upper(),
                "left_realization_id": left_id,
                "right_realization_id": right_id,
                "boundary_stop_id": left_stop,
                "boundary_graph_node_id": boundary_node,
                "left_occurrence_sequence": _seq(lo.get("stop_sequence")),
                "right_occurrence_sequence": _seq(ro.get("stop_sequence")),
                "left_evidence_type": str(lo.get("evidence_type", "")),
                "right_evidence_type": str(ro.get("evidence_type", "")),
                "boundary_location_status": status,
                "same_service_event_certified": False,
                "automatic_occurrence_merge_authorized": False,
                "vehicle_continuity": None,
                "passenger_continuity": None,
                "pickup_dropoff_semantics_assigned": False,
            })

    return catalog
