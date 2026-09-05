#!/usr/bin/env python3
"""Materialize the final 36 stop places against a supplied frozen road graph."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.phase2_final_stop_materialization_v3 import (
    CORE_MUNICIPALITY_COUNTS,
    EXPECTED_STOP_PLACE_COUNT,
    attach_stop_places_to_graph,
    validate_final_stop_places,
)

ROOT = Path(__file__).resolve().parents[1]
STOP_SOURCE_COMMIT = "ea30fbd18421164abaf2125033292cbe827e024d"
DEFAULT_STOPS = ROOT / "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv"
DEFAULT_STOP_VALIDATION = ROOT / "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_validation_gpt_v5.json"
DEFAULT_GRAPH_NODES = ROOT / "outputs/phase2/frozen_gate_d/graph_nodes.csv.gz"
DEFAULT_OUT = ROOT / "outputs/phase2/final_stop_materialization_v3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _relative_or_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stops", type=Path, default=DEFAULT_STOPS)
    parser.add_argument("--stop-validation", type=Path, default=DEFAULT_STOP_VALIDATION)
    parser.add_argument("--graph-nodes", type=Path, default=DEFAULT_GRAPH_NODES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    for path in (args.stops, args.stop_validation, args.graph_nodes):
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    source_validation = json.loads(args.stop_validation.read_text(encoding="utf-8"))
    if source_validation.get("status") != "PASS_OPERATIONAL_STOP_PLACE_LAYER":
        raise AssertionError("Final operational stop-place source is not PASS")
    if int(source_validation.get("stop_places_count", -1)) != EXPECTED_STOP_PLACE_COUNT:
        raise AssertionError("Source stop validation no longer certifies 36 stop places")
    if source_validation.get("by_municipality") != CORE_MUNICIPALITY_COUNTS:
        raise AssertionError("Source stop validation municipality counts changed")
    if source_validation.get("directional_boarding_points_exposed") is not False:
        raise AssertionError("Directional boarding-point identities must remain collapsed")
    if source_validation.get("routing_terminal_selected") is not False:
        raise AssertionError("Stop handoff must not preselect routing terminals")

    stops_raw = pd.read_csv(args.stops, dtype=str, keep_default_na=False)
    stops = validate_final_stop_places(stops_raw)
    graph_nodes = pd.read_csv(args.graph_nodes, dtype=str, keep_default_na=False, compression="infer")
    attachments = attach_stop_places_to_graph(stops, graph_nodes)

    args.out.mkdir(parents=True, exist_ok=True)
    output_csv = args.out / "stop_graph_attachments_v3.csv"
    output_frame = attachments.copy()
    output_frame["lat"] = output_frame["lat"].map(lambda value: f"{float(value):.9f}")
    output_frame["lon"] = output_frame["lon"].map(lambda value: f"{float(value):.9f}")
    output_frame["attachment_distance_m"] = output_frame["attachment_distance_m"].map(
        lambda value: f"{float(value):.9f}"
    )
    for column in ("route_ready", "service_class_automatic", "automatic_materialization_eligible"):
        output_frame[column] = output_frame[column].map(lambda value: str(bool(value)).lower())
    output_frame.to_csv(output_csv, index=False, lineterminator="\n")

    conventional = attachments.loc[attachments["service_class"].eq("CONVENTIONAL_TPL")].copy()
    special = attachments.loc[attachments["service_class"].ne("CONVENTIONAL_TPL")].copy()
    by_municipality = {
        municipality: int((attachments["municipality"] == municipality).sum())
        for municipality in CORE_MUNICIPALITY_COUNTS
    }
    checks = {
        "source_stop_layer_pass": source_validation.get("status") == "PASS_OPERATIONAL_STOP_PLACE_LAYER",
        "exactly_36_stop_places_preserved": len(attachments) == EXPECTED_STOP_PLACE_COUNT,
        "stable_stop_place_ids_unique": bool(attachments["stop_place_id"].is_unique),
        "municipality_counts_match_final_handoff": by_municipality == CORE_MUNICIPALITY_COUNTS,
        "all_conventional_stop_places_route_ready_on_current_graph": bool(conventional["route_ready"].all()),
        "no_unresolved_conventional_attachment_on_current_graph": not bool(
            conventional["attachment_status"].isin(["REVIEW_75_250M", "OUTSIDE_250M"]).any()
        ),
        "special_service_not_automatically_promoted": not bool(
            special["automatic_materialization_eligible"].any()
        ) if len(special) else True,
        "all_36_identities_have_explicit_attachment_status": bool(
            attachments["attachment_status"].astype(str).str.len().gt(0).all()
        ),
    }
    status = "PASS_FINAL_STOP_MATERIALIZATION_V3" if all(checks.values()) else "FAIL_FINAL_STOP_MATERIALIZATION_V3"
    graph_epochs = sorted(set(attachments["graph_epoch_id"].astype(str)))

    validation = {
        "status": status,
        "contract": "FINAL_36_STOP_PLACES_IDENTITY_FROZEN_GRAPH_ATTACHMENT_RERUNNABLE_CORRIDOR_MATERIALIZATION_READY",
        "source_handoff_commit": STOP_SOURCE_COMMIT,
        "inputs": {
            "stop_places": _relative_or_text(args.stops),
            "stop_places_sha256": sha256(args.stops),
            "stop_validation": _relative_or_text(args.stop_validation),
            "stop_validation_sha256": sha256(args.stop_validation),
            "graph_nodes": _relative_or_text(args.graph_nodes),
            "graph_nodes_sha256": sha256(args.graph_nodes),
            "graph_epoch_id": graph_epochs[0] if len(graph_epochs) == 1 else graph_epochs,
        },
        "counts": {
            "stop_places_total": int(len(attachments)),
            "conventional_tpl": int(len(conventional)),
            "special_or_other_service": int(len(special)),
            "route_ready_le_75m": int(attachments["route_ready"].sum()),
            "review_75_250m": int((attachments["attachment_status"] == "REVIEW_75_250M").sum()),
            "outside_250m": int((attachments["attachment_status"] == "OUTSIDE_250M").sum()),
            "automatic_materialization_eligible": int(attachments["automatic_materialization_eligible"].sum()),
            "by_municipality": by_municipality,
        },
        "checks": checks,
        "guards": {
            "candidate_network_generated": False,
            "route_topology_selected": False,
            "structural_anchor_promoted_to_passenger_stop": False,
            "new_stop_created": False,
            "obsolete_43_stop_bridge_active": False,
            "directional_boarding_point_identity_restored": False,
            "interchange_logic_added": False,
            "special_service_auto_promoted": False,
            "primary_or_runner_up_selected": False,
            "rt017_graph_rebind_required_before_final_territorial_search": True,
        },
        "current_graph_role": "COMPATIBILITY_SMOKE_PRE_RT017_NOT_FINAL_TERRITORIAL_BINDING",
        "downstream_rule": (
            "Re-run this attachment stage on the frozen RT-017 graph, then materialize exact stop occurrences "
            "only from ordered corridor path nodes. RT-014 receives explicit resulting stop IDs/coordinates; "
            "it must not infer stops."
        ),
        "output": {
            "attachments": _relative_or_text(output_csv),
            "attachments_sha256": sha256(output_csv),
        },
    }
    validation_path = args.out / "final_stop_materialization_v3_validation.json"
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    if status.startswith("FAIL"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
