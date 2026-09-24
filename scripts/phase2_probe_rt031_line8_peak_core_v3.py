"""Pinned road-only probe of an FS/south/San Zeno peak short circuit.

No proposed stop, safe turn, public service or timetable is certified here.
"""

import argparse
from decimal import Decimal
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, rows
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe


FS = "FROZEN::L00407"


def build(paths):
    edges, nodes, rules, attachments = build_graph(paths)
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    repair = json.loads(paths["repair"].read_text(encoding="utf-8"))
    policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
    if (road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or repair["contract"] != "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3"
            or policy["contract"] != "PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3"):
        raise ValueError("source contract drift")
    if any(source["network_selected"] for source in (road, repair)):
        raise ValueError("source unexpectedly selected a network")
    if repair["source_sha256"]["road_screen"] != digest(paths["road_screen"], True):
        raise ValueError("pinned road screen drift")
    candidate = next(row for row in rows(paths["candidates_normalized_newlines"])
                     if row["candidate_id"] == "P2V2S_0031")
    if candidate["physical_status"] != "FIELD_CHECK_PENDING":
        raise ValueError("south site status drift")
    if road["north_proxy"]["boarding_stop_certified"] is not False:
        raise ValueError("north proxy unexpectedly certified")
    attachment_nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
                        if row["route_ready"] == "True"}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    sequences = {
        "south_only": [("FS", FS), ("Olgiate sud", VIRTUAL), ("FS", FS)],
        "north_only": [("FS", FS), ("San Zeno", NORTH), ("FS", FS)],
        "south_then_north": [("FS", FS), ("Olgiate sud", VIRTUAL),
                             ("FS", FS), ("San Zeno", NORTH), ("FS", FS)],
    }
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_way_ids = {way for relation in successor["successor_via_way_relations"]
                   for way in relation["via_way_ids"]}
    loops = {}
    for name, sequence in sequences.items():
        path = screen_lobe(sequence, attachment_nodes, edges, rules)
        if not path["reachable"] or path["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]:
            raise ValueError(f"short circuit not legal under represented via-node rules: {name}")
        if via_way_ids & set(path["osm_way_ids"]):
            raise ValueError(f"short circuit touches unresolved successor via-way: {name}")
        stops = sorted(path_stops(path, edges, eligible))
        if stops != [FS]:
            raise ValueError(f"unexpected existing inventory stop encounter: {name}")
        loops[name] = {
            "ordered_waypoints": path["ordered_waypoints"],
            "distance_m": path["distance_m"],
            "running_minutes_model_excluding_dwell_recovery": path["running_minutes_model"],
            "directed_edge_count": path["path_edge_count"],
            "ordered_edge_id_sha256": path["path_edge_id_sha256"],
            "existing_inventory_stop_ids_encountered_not_boarding_guaranteed": stops,
            "represented_via_node_bad_turn_count": 0,
            "known_successor_via_way_overlap": [],
        }
    if abs(loops["south_only"]["distance_m"] + loops["north_only"]["distance_m"]
           - loops["south_then_north"]["distance_m"]) > .002:
        raise ValueError("composed short circuit distance mismatch")
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    days = Decimal(260)
    peak_loops = Decimal(8)
    core_km = Decimal(str(loops["south_then_north"]["distance_m"])) / 1000
    inclusive = repair["combined_repair_order_options"]["FIVE_QUATTRO_STRADE_THEN_CARIPLO"]
    inclusive_pair_km = (Decimal(str(inclusive["forward_complete_cycle_distance_m"]))
                         + Decimal(str(inclusive["reverse_complete_cycle_distance_m"]))) / 1000
    extensions = {}
    nominated_pairs = {
        "OLGIATE_STATALE_CALCO_VIRGILIO": (
            "ASF::OLGIATE_MOLGORA_VIA_STATALE", "ASF::CALCO_VIA_GARIBALDI"),
        "OLGIATE_SALUTE_CALCO_VIRGILIO": (
            "ASF::OLGIATE_MOLGORA_VIA_DELLA_SALUTE", "ASF::CALCO_VIA_GARIBALDI"),
        "SCARPONE_CALCO_VIRGILIO": (
            "ASF::OLGIATE_MOLGORA_SCARPONE", "ASF::CALCO_VIA_GARIBALDI"),
    }
    for name, (left, right) in nominated_pairs.items():
        if left not in attachment_nodes or right not in attachment_nodes:
            raise ValueError(f"nominated stop attachment missing: {name}")
        base = sequences["south_then_north"]
        best = None
        for left_index in range(1, len(base)):
            once = base[:left_index] + [(attachments[left]["stop_name"], left)] + base[left_index:]
            for right_index in range(1, len(once)):
                sequence = (once[:right_index] + [(attachments[right]["stop_name"], right)]
                            + once[right_index:])
                path = screen_lobe(sequence, attachment_nodes, edges, rules)
                if (not path["reachable"]
                        or path["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]
                        or via_way_ids & set(path["osm_way_ids"])):
                    continue
                key = (path["distance_m"], left_index, right_index)
                if best is None or key < best[0]:
                    best = (key, path)
        if best is None:
            raise ValueError(f"no represented-via-node-legal insertion: {name}")
        path = best[1]
        annual = days * (inclusive_pair_km * 7
                         + Decimal(str(path["distance_m"])) / 1000 * peak_loops)
        extensions[name] = {
            "nominated_existing_stop_ids": [left, right],
            "ordered_waypoints": path["ordered_waypoints"],
            "shortest_found_distance_m_for_fixed_waypoint_set": path["distance_m"],
            "running_minutes_model_excluding_dwell_recovery": path["running_minutes_model"],
            "existing_inventory_stop_ids_encountered_not_boarding_guaranteed": sorted(
                path_stops(path, edges, eligible)),
            "annual_km_with_seven_inclusive_full_pairs_and_eight_short_loops_before_extras": float(annual),
            "margin_to_approved_cap_before_extras_km": float(cap - annual),
            "within_cap_before_extras": annual <= cap,
            "ordered_edge_id_sha256": path["path_edge_id_sha256"],
        }
    examples = []
    for variant_id in ("FIVE_QUATTRO_STRADE_THEN_CARIPLO",
                       "FOUR_QUATTRO_STRADE_THEN_CARIPLO"):
        variant = repair["combined_repair_order_options"][variant_id]
        pair_km = (Decimal(str(variant["forward_complete_cycle_distance_m"]))
                   + Decimal(str(variant["reverse_complete_cycle_distance_m"]))) / 1000
        for full_pairs in (7, 8):
            annual = days * (pair_km * full_pairs + core_km * peak_loops)
            examples.append({
                "variant_id": variant_id,
                "full_forward_and_reverse_pairs_per_day": full_pairs,
                "additional_short_core_loops_per_day": int(peak_loops),
                "annual_model_km_before_all_extras": float(annual),
                "margin_to_approved_cap_before_all_extras_km": float(cap - annual),
                "within_cap_before_all_extras": annual <= cap,
            })
    return {
        "contract": "RT031_LINE8_PEAK_SHORT_CORE_ROAD_PROBE_V3",
        "status": "NON_DECISIONAL_ROAD_AND_DISTANCE_ARITHMETIC_ONLY",
        "source_sha256": {key: digest(paths[key], key in (
            "anchor", "candidates_normalized_newlines", "road_screen", "repair", "policy"))
                          for key in paths},
        "loops": loops,
        "fixed_waypoint_short_core_extensions": extensions,
        "extension_scope": "Shortest found insertion order for each nominated existing-stop pair only; not an exhaustive corridor search or passenger-service selection.",
        "annual_examples": examples,
        "annual_cap_km_not_decision_budget_km": float(cap),
        "assumed_annual_service_days": int(days),
        "peak_short_loops_count_assumption": int(peak_loops),
        "peak_short_loops_intended_context": "8 departures in four half-open hours; H30 at each new site only if safe directional stop events and phases are certified",
        "not_certified": ["physical stop at south site", "physical stop at San Zeno",
                          "vehicle turning, width and suitability",
                          "full-history legal route composition", "passenger service continuity at FS",
                          "dwell/recovery-inclusive cycle, fleet and scheduled H30",
                          "rail connections, depot km and Saturday service",
                          "temporal access for outer localities"],
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "anchor", "road_screen", "repair", "policy"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "anchor", "road_screen",
                                             "repair", "policy")}, args.output)
