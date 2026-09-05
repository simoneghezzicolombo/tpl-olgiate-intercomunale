from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.phase2_complete_directed_pairs_v3 import build_complete_directed_pair_manifest, directed_pair_id
from src.phase2_elementary_corridor_reduction_v3 import (
    build_pair_query_anchor_table,
    build_reciprocal_elementary_structural_links,
)

ROOT = Path(__file__).resolve().parents[1]
ATTACHMENTS = ROOT / "outputs/phase2/final_stop_materialization_v3/stop_graph_attachments_v3.csv"
OUTDIR = ROOT / "outputs/phase2/elementary_corridor_reduction_v3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def corridor(cid: str, source: str, target: str, nodes: list[str]) -> dict:
    return {
        "corridor_id": cid,
        "pair_id": directed_pair_id(source, target),
        "source_routing_terminal_id": source,
        "target_routing_terminal_id": target,
        "path_node_ids": ";".join(nodes),
        "admissible_for_corridor_pool": True,
        "running_minutes_model": 5.0,
        "distance_m": 1000.0,
    }


def occurrence(cid: str, seq: int, pos: int, stop_id: str) -> dict:
    return {
        "corridor_id": cid,
        "stop_sequence": seq,
        "path_node_position": pos,
        "stop_place_id": stop_id,
        "service_class": "CONVENTIONAL_TPL",
    }


def pair_row(source: str, target: str) -> dict:
    return {
        "pair_id": directed_pair_id(source, target),
        "source_routing_terminal_id": source,
        "target_routing_terminal_id": target,
        "gate_d_route_found": True,
    }


def main() -> None:
    if not ATTACHMENTS.exists():
        raise FileNotFoundError(ATTACHMENTS)

    attachments = pd.read_csv(ATTACHMENTS)
    anchors = build_pair_query_anchor_table(attachments)
    manifest_result = build_complete_directed_pair_manifest(anchors)
    manifest = manifest_result["manifest"]

    fixture_pairs = pd.DataFrame([
        pair_row("A", "B"),
        pair_row("B", "A"),
        pair_row("A", "C"),
        pair_row("C", "A"),
    ])
    fixture_corridors = pd.DataFrame([
        corridor("C_AB", "A", "B", ["NA", "NB"]),
        corridor("C_BA", "B", "A", ["NB", "NA"]),
        corridor("C_AC", "A", "C", ["NA", "NB", "NC"]),
        corridor("C_CA", "C", "A", ["NC", "NA"]),
    ])
    fixture_occurrences = pd.DataFrame([
        occurrence("C_AB", 1, 0, "A"),
        occurrence("C_AB", 2, 1, "B"),
        occurrence("C_BA", 1, 0, "B"),
        occurrence("C_BA", 2, 1, "A"),
        occurrence("C_AC", 1, 0, "A"),
        occurrence("C_AC", 2, 1, "B"),
        occurrence("C_AC", 3, 2, "C"),
        occurrence("C_CA", 1, 0, "C"),
        occurrence("C_CA", 2, 1, "A"),
    ])
    fixture = build_reciprocal_elementary_structural_links(
        fixture_pairs, fixture_corridors, fixture_occurrences
    )

    checks = {
        "rt018_attachment_has_36_rows": len(attachments) == 36,
        "anchor_manifest_has_35_conventional_rows": len(anchors) == 35,
        "special_service_excluded_from_automatic_anchor_manifest": "SPECIAL_SERVICE" not in set(anchors["service_class"]),
        "all_anchor_rows_explicitly_not_service_termini": anchors["service_terminal_status_claimed"].eq(False).all(),
        "rt010_complete_pair_manifest": manifest_result["complete"],
        "rt010_directed_pair_count_is_1190": len(manifest) == 1190,
        "rt010_unordered_pair_count_is_595": manifest_result["unordered_pair_count"] == 595,
        "fixture_ab_reciprocal_elementary_link_exists": len(fixture["structural_links"]) == 1,
        "fixture_ac_direction_is_decomposable": not bool(
            fixture["classification"].loc[
                fixture["classification"]["corridor_id"] == "C_AC",
                "elementary_for_structural_reduction",
            ].iloc[0]
        ),
        "no_service_terminal_claim_in_reciprocity_metadata": not fixture["metadata"]["service_terminal_status_claimed"],
        "real_territorial_graph_blocked_pending_rt017": True,
    }
    # pandas/numpy reductions may return numpy.bool_; normalize the audit payload
    # to built-in bools before JSON serialization and before the fail-closed gate.
    checks = {key: bool(value) for key, value in checks.items()}
    if not all(checks.values()):
        raise AssertionError(checks)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    anchors.to_csv(OUTDIR / "pair_query_anchor_manifest_v3.csv", index=False, lineterminator="\n")
    manifest.to_csv(OUTDIR / "complete_directed_pair_manifest_v3.csv", index=False, lineterminator="\n")
    fixture["classification"].to_csv(OUTDIR / "controlled_fixture_elementarity_v3.csv", index=False, lineterminator="\n")
    fixture["pair_audit"].to_csv(OUTDIR / "controlled_fixture_reciprocity_pair_audit_v3.csv", index=False, lineterminator="\n")

    validation = {
        "status": "PASS_RT019_TECHNICAL_PAIR_QUERY_ANCHORS_AND_ELEMENTARY_CORRIDOR_REDUCTION_V3",
        "contract": "TECHNICAL_PAIR_QUERY_ANCHORS_AND_ELEMENTARY_CORRIDOR_INTERFACE_NOT_SERVICE_TERMINAL_SELECTION",
        "checks": checks,
        "counts": {
            "final_stop_places": int(len(attachments)),
            "technical_pair_query_anchors": int(len(anchors)),
            "complete_directed_pair_requests": int(len(manifest)),
            "unordered_pair_identities": int(manifest_result["unordered_pair_count"]),
        },
        "guards": {
            "service_terminus_or_capolinea_selected": False,
            "route_topology_selected": False,
            "figure_eight_forced": False,
            "timetable_or_headway_selected": False,
            "special_service_auto_included": False,
            "interchange_logic_added": False,
            "primary_or_runner_up_selected": False,
            "rt017_rebind_required_before_territorial_use": True,
        },
        "territorial_status": "BLOCKED_PENDING_RT017_PASS_CORRIDOR_CORPUS",
        "inputs": {
            "rt018_attachments": str(ATTACHMENTS.relative_to(ROOT)),
            "rt018_attachments_sha256": sha256(ATTACHMENTS),
        },
    }
    payload = json.dumps(validation, indent=2, sort_keys=True) + "\n"
    (OUTDIR / "elementary_corridor_reduction_v3_validation.json").write_text(
        payload, encoding="utf-8"
    )
    print(payload, end="")


if __name__ == "__main__":
    main()
