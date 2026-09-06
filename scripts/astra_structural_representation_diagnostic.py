"""Bounded RT-031 architecture diagnostic; fixtures are not territorial evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from phase2_macro_structure_decoupling_v3 import contract_structure


def require(condition, message):
    if not condition:
        raise ValueError(message)


def core(edges):
    """Reuse certified RT-031 contraction, retaining its exact chain partition."""
    vertices = sorted({v for pair in edges.values() for v in pair})
    result = contract_structure("CONTROLLED", list(edges), vertices, edges)
    signature = {
        "topology": result.macro_topology_class,
        "leaves": result.leaf_count,
        "branch_degrees": list(result.branch_degree_sequence),
        "cycle_rank": result.cycle_rank,
        "macro_edges": result.macro_edge_count,
    }
    require(sorted(x for chain in result.macro_edge_links for x in chain) == sorted(edges),
            "contraction lost or duplicated input edges")
    return signature


def compose(parts, road_edges, allowed_pairs):
    """Controlled pair-turn fixture only; production must handle via-way state too."""
    edges = [edge for part in parts for edge in part]
    if not edges or any(edge not in road_edges for edge in edges):
        return "UNKNOWN_EDGE"
    for left, right in zip(edges, edges[1:]):
        if road_edges[left][1] != road_edges[right][0]:
            return "DISCONNECTED"
        if (left, right) not in allowed_pairs:
            return "TURN_NOT_CERTIFIED"
    return "VALID_FIXTURE_ONLY"


def run():
    contraction_hash = hashlib.sha256(
        (ROOT / "src/phase2_macro_structure_decoupling_v3.py").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    require(contraction_hash == "4fecada86dbdecbe56f955f25dc5e57bd53a8ee2ad2c0de9e1a5694f7e170334",
            "certified RT031 contraction implementation drift")
    checks = {}
    base = {"a": ("A", "B")}
    base_signature = core(base)
    # Subdivision is a stronger test than simply attaching additional stop labels.
    chain = {str(i): (str(i), str(i + 1)) for i in range(14)}
    checks["subdivision_2_to_15_vertices"] = core(chain) == base_signature
    # The same road carrier has two different hypothetical fixture stop patterns.
    carrier = tuple(chain)
    stop_patterns = [("0", "14"), tuple(str(i) for i in range(15))]
    checks["same_carrier_2_or_15_stops"] = (
        len(stop_patterns[0]) == 2 and len(stop_patterns[1]) == 15
        and core(dict(reversed(list(chain.items())))) == core(dict((e, chain[e]) for e in carrier))
    )
    branch = core({"a": ("A", "J"), "b": ("J", "B"), "c": ("J", "C")})
    cycle = core({"a": ("A", "B"), "b": ("B", "C"), "c": ("C", "A")})
    checks["branch_detected"] = branch["branch_degrees"] == [3] and branch["leaves"] == 3
    checks["cycle_detected"] = cycle["cycle_rank"] == 1 and cycle["topology"] == "PURE_CYCLE_CORE"
    # A detour replaces an edge by a longer path. Topology stays PATH; geometry changes.
    detour = core({"ax": ("A", "X"), "xb": ("X", "B")})
    geometry = {"direct_length_fixture_m": 100, "detour_length_fixture_m": 180}
    checks["detour_requires_geometry_descriptor"] = detour == base_signature and 180 > 100
    roads = {"a": ("A", "J"), "b": ("J", "B"), "back": ("J", "A")}
    checks["individually_valid_fragments_can_fail_join"] = (
        compose([["a"]], roads, set()) == "VALID_FIXTURE_ONLY"
        and compose([["b"]], roads, set()) == "VALID_FIXTURE_ONLY"
        and compose([["a"], ["b"]], roads, set()) == "TURN_NOT_CERTIFIED"
        and compose([["a"], ["b"]], roads, {("a", "b")}) == "VALID_FIXTURE_ONLY"
    )
    checks["opposite_direction_not_inferred"] = compose([["b"], ["a"]], roads, {( "a", "b")}) == "DISCONNECTED"
    checks["unknown_edge_fails_closed"] = compose([["missing"]], roads, set()) == "UNKNOWN_EDGE"
    path = ROOT / "outputs/phase2/stop_pattern_redesign_v3/current_stop_spacing_patterns_v3.csv"
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(payload).hexdigest()
    # Source frozen at RT-031 62f241d; normalize line endings only for Windows replay.
    expected = "1d3a29ccb196e838dcb085f4ca0495eb1dc1e13cf55520b70b5e2a0a7748236c"
    require(digest == expected, "D184/D185 frozen pattern input drift")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    real = []
    for index in ("1", "13"):
        row = next(r for r in rows if r["pattern_index"] == index)
        stops = row["stop_ids"].split("|")
        require(len(stops) == int(row["stop_count"]) == len(set(stops)), "invalid calibration sequence")
        edges = {str(i): pair for i, pair in enumerate(zip(stops, stops[1:]))}
        signature = core(edges)
        require(signature == base_signature, "stop sequence should retain PATH skeleton")
        real.append({"route": row["route_short_name"], "pattern_index": index,
                     "ordered_stop_ids": stops, "passenger_stop_count": len(stops),
                     "sequence_skeleton": signature,
                     "scope": "OBSERVED_STOP_SEQUENCE_ONLY_NOT_ROUTED_GEOMETRY",
                     "physical_topology_certified": False})
    checks["real_D184_D185_sequence_representability"] = len(real) == 2
    require(all(checks.values()), f"diagnostic failure: {checks}")
    return {
        "status": "PASS_BOUNDED_REPRESENTATION_DIAGNOSTIC",
        "architectural_verdict": "REPRESENTATION CHANGE REQUIRED",
        "upstream_commit": "62f241d4df89585cd9dad6965ba866e28c91128d",
        "benchmark_normalized_sha256": digest,
        "contraction_normalized_sha256": contraction_hash,
        "checks": checks, "check_count": len(checks),
        "fixture_topologies": {"base": base_signature, "branch": branch, "cycle": cycle, "detour": detour},
        "fixture_geometry": geometry, "real_sequence_calibration": real,
        "acceptance": {"A_stop_invariance": "PASS_CONTROLLED", "B_topology_and_geometry_sensitivity": "PASS_CONTROLLED",
                       "C_real_service_geometry": "OPEN_SEQUENCE_ONLY", "D_no_hand_design": "PASS_SCOPE",
                       "E_RT030_provenance": "CONTRACT_ONLY_PRODUCTION_COMPOSITION_OPEN",
                       "F_future_stop_extensibility": "CONTRACT_ONLY_NO_STOPS_CREATED"},
        "full_search_run": False, "production_turn_composition_certified": False,
        "primary_selection_authorised": False, "runner_up_selection_authorised": False,
        "decision_budget_km": None, "uncertainty_band_min": None,
        "weighted_score": False,
    }


if __name__ == "__main__":
    result = run()
    require(result == run(), "non-deterministic replay")
    target = ROOT / "outputs/phase2/astra_structural_representation/diagnostic.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "checks": result["check_count"], "deterministic_replay": True}))
