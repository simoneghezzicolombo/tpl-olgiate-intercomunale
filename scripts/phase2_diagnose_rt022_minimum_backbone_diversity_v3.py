#!/usr/bin/env python3
"""Build a descriptive, non-decisional diversity diagnostic for RT-022 minimum backbones."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from itertools import combinations
from pathlib import Path

import pandas as pd

PASS_STATUS = "PASS_NONDECISIONAL_RT022_STRUCTURAL_DIVERSITY_DIAGNOSTIC"
EXPECTED_STRUCTURE_SHA256 = "1d6ccd18a5707aa8e2e51b1eefcc9d27056678f0d5e260c9027d1414a1ddf8d7"


def _split(value: object) -> list[str]:
    return [x for x in str(value).split(";") if x]


def _canonical_frame_sha256(frame: pd.DataFrame) -> str:
    if frame.empty:
        payload = b""
    else:
        ordered = frame.sort_values(list(frame.columns), kind="mergesort").reset_index(drop=True)
        payload = ordered.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_connected(nodes: set[str], edges: list[tuple[str, str]], removed: str | None = None) -> bool:
    remaining = sorted(nodes - ({removed} if removed else set()))
    if len(remaining) <= 1:
        return True
    adjacency: dict[str, set[str]] = {node: set() for node in remaining}
    for a, b in edges:
        if a == removed or b == removed:
            continue
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)
    seen = {remaining[0]}
    stack = [remaining[0]]
    while stack:
        node = stack.pop()
        for nxt in adjacency[node] - seen:
            seen.add(nxt)
            stack.append(nxt)
    return seen == set(remaining)


def build_diagnostic(structures: pd.DataFrame, links: pd.DataFrame, stops: pd.DataFrame, audit: dict) -> dict:
    if audit.get("status") != "PASS_EXACT_MINIMUM_TOPOLOGY_NEUTRAL_TERRITORIAL_BACKBONE_UNIVERSE":
        raise ValueError("RT-022 minimum-backbone audit is not certified PASS")
    if audit.get("digests", {}).get("structure_universe_sha256") != EXPECTED_STRUCTURE_SHA256:
        raise ValueError("unexpected RT-022 structure-universe identity")
    if len(structures) != 88 or len(links) != 110:
        raise ValueError("unexpected frozen RT-022 row counts")

    stop_by_id = stops.set_index("stop_place_id", drop=False)
    link_by_id = links.set_index("structural_link_id", drop=False)
    vertex_counts: collections.Counter[str] = collections.Counter()
    edge_family_occurrences: collections.Counter[tuple[str, str]] = collections.Counter()
    municipality_skeletons: collections.Counter[tuple[tuple[str, str], ...]] = collections.Counter()
    articulation_counts: collections.Counter[str] = collections.Counter()
    olgiate_degree: collections.Counter[int] = collections.Counter()

    for row in structures.itertuples(index=False):
        vertices = _split(row.vertex_ids)
        link_ids = _split(row.link_ids)
        vertex_counts.update(vertices)
        municipality_edges: list[tuple[str, str]] = []
        for link_id in link_ids:
            if link_id not in link_by_id.index:
                raise ValueError(f"unknown structural link {link_id}")
            link = link_by_id.loc[link_id]
            for terminal in (link.terminal_a, link.terminal_b):
                if terminal not in stop_by_id.index:
                    raise ValueError(f"unknown stop-place terminal {terminal}")
            ma = str(stop_by_id.loc[link.terminal_a, "municipality"])
            mb = str(stop_by_id.loc[link.terminal_b, "municipality"])
            pair = tuple(sorted((ma, mb)))
            if ma == mb:
                raise ValueError("accepted minimum backbone unexpectedly contains same-municipality link")
            municipality_edges.append(pair)
            edge_family_occurrences[pair] += 1
        skeleton = tuple(sorted(municipality_edges))
        municipality_skeletons[skeleton] += 1

        municipality_nodes = {m for edge in municipality_edges for m in edge}
        degree: collections.Counter[str] = collections.Counter()
        for a, b in municipality_edges:
            degree[a] += 1
            degree[b] += 1
        olgiate_degree[degree["Olgiate Molgora"]] += 1
        for municipality in sorted(municipality_nodes):
            if not _is_connected(municipality_nodes, municipality_edges, removed=municipality):
                articulation_counts[municipality] += 1

    municipalities = sorted(stops["municipality"].dropna().astype(str).unique())
    terminal_options: dict[str, dict] = {}
    for municipality in municipalities:
        details = []
        for stop_id, count in vertex_counts.items():
            stop = stop_by_id.loc[stop_id]
            if stop["municipality"] != municipality:
                continue
            details.append({
                "stop_place_id": stop_id,
                "stop_name": str(stop["stop_name"]),
                "municipality": municipality,
                "structure_count": int(count),
                "structure_share": round(count / len(structures), 9),
            })
        details.sort(key=lambda x: (-x["structure_count"], x["stop_name"], x["stop_place_id"]))
        terminal_options[municipality] = {
            "distinct_terminal_stop_places": len(details),
            "terminal_stop_places": details,
        }

    all_link_families: collections.Counter[tuple[str, str]] = collections.Counter()
    for link in links.itertuples(index=False):
        ma = str(stop_by_id.loc[link.terminal_a, "municipality"])
        mb = str(stop_by_id.loc[link.terminal_b, "municipality"])
        all_link_families[tuple(sorted((ma, mb)))] += 1

    cross = {
        f"{a} | {b}": int(count)
        for (a, b), count in sorted(all_link_families.items())
        if a != b
    }
    same = {municipality: int(all_link_families.get((municipality, municipality), 0)) for municipality in municipalities}
    skeleton_rows = [
        {
            "edge_families": [f"{a} | {b}" for a, b in skeleton],
            "structure_count": int(count),
            "structure_share": round(count / len(structures), 9),
        }
        for skeleton, count in sorted(municipality_skeletons.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        "status": PASS_STATUS,
        "semantics": "DESCRIPTIVE_ONLY_NOT_CANDIDATE_RANKING_OR_SERVICE_DESIGN",
        "scope": "CERTIFIED_88_EXACT_MINIMUM_POLICY_BACKBONES_ONLY",
        "structure_universe_sha256": EXPECTED_STRUCTURE_SHA256,
        "counts": {
            "structures": int(len(structures)),
            "reciprocal_structural_links": int(len(links)),
            "distinct_terminal_stop_places_used": int(len(vertex_counts)),
            "unique_municipality_skeletons": int(len(municipality_skeletons)),
            "accepted_structure_edge_occurrences": int(sum(edge_family_occurrences.values())),
        },
        "topology_descriptive_post_generation": {
            "by_class": {str(k): int(v) for k, v in structures["topology_class"].value_counts().items()},
            "by_max_degree": {str(k): int(v) for k, v in structures["max_degree"].value_counts().sort_index().items()},
        },
        "terminal_options_by_municipality": terminal_options,
        "cross_municipality_reciprocal_link_families_available": {
            "family_count": len(cross),
            "link_count_by_family": cross,
        },
        "same_municipality_reciprocal_links_available": same,
        "municipality_edge_family_occurrences_in_88_backbones": {
            f"{a} | {b}": int(count) for (a, b), count in sorted(edge_family_occurrences.items())
        },
        "municipality_skeletons": skeleton_rows,
        "municipality_articulation_occurrences": {
            municipality: int(articulation_counts.get(municipality, 0)) for municipality in municipalities
        },
        "olgiate_molgora_degree_distribution_in_88_backbones": {
            str(k): int(v) for k, v in sorted(olgiate_degree.items())
        },
        "guards": {
            "winner_selected": False,
            "primary_runner_up_selected": False,
            "service_terminus_selected": False,
            "topology_prior_introduced": False,
            "passenger_access_quality_inferred": False,
            "five_plus_edge_structures_declared_inferior": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structures", type=Path, required=True)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--stops", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    diagnostic = build_diagnostic(
        pd.read_csv(args.structures),
        pd.read_csv(args.links),
        pd.read_csv(args.stops),
        json.loads(args.audit.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
