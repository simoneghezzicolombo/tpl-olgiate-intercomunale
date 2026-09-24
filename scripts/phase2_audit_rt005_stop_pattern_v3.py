#!/usr/bin/env python3
"""Audit the current Phase 2 finalists for RT-005 stop-pattern formulation failure.

This audit does not build a replacement network. It demonstrates, from pinned
repository outputs, whether the current finalist route structures are safe to
interpret as realistic passenger stop patterns.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

STUDY_MUNICIPALITIES = (
    "Olgiate Molgora",
    "Calco",
    "Brivio",
    "Santa Maria Hoè",
    "La Valletta Brianza",
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise_text(value: str) -> str:
    value = value.replace("HoÃ¨", "Hoè")
    value = unicodedata.normalize("NFC", value.strip())
    return re.sub(r"\s+", " ", value)


def split_municipalities(value: str) -> list[str]:
    raw = normalise_text(value)
    if not raw:
        return []
    tokens = re.split(r"\s*[;|]\s*", raw)
    return [normalise_text(token) for token in tokens if normalise_text(token)]


def load_anchor_universe(path: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"anchor_id", "evidence_status", "source_kind", "municipalities"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Anchor universe missing fields: {sorted(missing)}")
        for row in reader:
            anchor_id = str(row["anchor_id"]).strip()
            if not anchor_id:
                raise ValueError("Blank anchor_id in routing anchor universe")
            if anchor_id in out:
                raise ValueError(f"Duplicate anchor_id {anchor_id}")
            out[anchor_id] = {
                "evidence_status": str(row["evidence_status"]).strip(),
                "source_kind": str(row["source_kind"]).strip(),
                "municipalities": split_municipalities(str(row["municipalities"])),
                "source_members": str(row.get("source_members", "")).strip(),
            }
    return out


def parse_json_list(value: str, field: str, line_no: int) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be list[str] at line {line_no}")
    return parsed


def load_finalists(path: Path) -> dict[str, dict[str, object]]:
    finalists: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "finalist_alias", "topology_family", "service_span_min",
            "public_route_ordinal", "anchors_json", "anchor_labels_json",
            "sequence_semantics",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Finalist route structure missing fields: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            alias = str(row["finalist_alias"]).strip()
            anchors = parse_json_list(str(row["anchors_json"]), "anchors_json", line_no)
            labels = parse_json_list(str(row["anchor_labels_json"]), "anchor_labels_json", line_no)
            if len(anchors) != len(labels):
                raise ValueError(f"Anchor/label length mismatch at line {line_no}")
            entry = finalists.setdefault(alias, {
                "topology_family": str(row["topology_family"]).strip(),
                "service_span_min": int(row["service_span_min"]),
                "routes": [],
            })
            if entry["topology_family"] != str(row["topology_family"]).strip():
                raise ValueError(f"Topology drift within finalist {alias}")
            if entry["service_span_min"] != int(row["service_span_min"]):
                raise ValueError(f"Span drift within finalist {alias}")
            entry["routes"].append({
                "ordinal": int(row["public_route_ordinal"]),
                "anchors": anchors,
                "labels": labels,
                "sequence_semantics": str(row["sequence_semantics"]).strip(),
            })
    return finalists


def audit_finalist(alias: str, payload: dict[str, object], anchor_universe: dict[str, dict[str, object]]) -> dict[str, object]:
    routes = sorted(payload["routes"], key=lambda row: row["ordinal"])
    unique_nonhub: set[str] = set()
    technical_label_anchors: set[str] = set()
    field_check_pending: set[str] = set()
    municipalities: set[str] = set()
    missing_anchor_metadata: set[str] = set()
    route_rows: list[dict[str, object]] = []

    for route in routes:
        route_nonhub: list[str] = []
        for anchor_id, label in zip(route["anchors"], route["labels"]):
            if anchor_id.startswith("rail:"):
                continue
            route_nonhub.append(anchor_id)
            unique_nonhub.add(anchor_id)
            metadata = anchor_universe.get(anchor_id)
            if metadata is None:
                missing_anchor_metadata.add(anchor_id)
                continue
            municipalities.update(metadata["municipalities"])
            if "FIELD_CHECK_PENDING" in str(metadata["evidence_status"]):
                field_check_pending.add(anchor_id)
            if normalise_text(label) == normalise_text(anchor_id) or re.fullmatch(r"P2V2S_\d+", normalise_text(label)):
                technical_label_anchors.add(anchor_id)
        route_rows.append({
            "ordinal": route["ordinal"],
            "sequence_semantics": route["sequence_semantics"],
            "nonhub_explicit_anchor_count": len(set(route_nonhub)),
            "ordered_nonhub_anchors": route_nonhub,
        })

    study_served = sorted(m for m in STUDY_MUNICIPALITIES if m in municipalities)
    study_missing = sorted(m for m in STUDY_MUNICIPALITIES if m not in municipalities)
    failure_reasons: list[str] = []
    if study_missing:
        failure_reasons.append("MISSING_STUDY_MUNICIPALITY_EXPLICIT_STOP")
    if technical_label_anchors:
        failure_reasons.append("TECHNICAL_ID_SURVIVES_AS_STOP_LABEL")
    if field_check_pending:
        failure_reasons.append("FIELD_CHECK_PENDING_STOP_IN_FINALIST")
    if any(row["sequence_semantics"] == "ORDERED_CERTIFIED_ANCHORS_ONLY_NO_ROUTED_GEOMETRY" for row in route_rows):
        failure_reasons.append("ANCHOR_SEQUENCE_NOT_FULL_ROUTED_STOP_PATTERN")

    return {
        "finalist_alias": alias,
        "topology_family": payload["topology_family"],
        "service_span_min": payload["service_span_min"],
        "public_route_count": len(routes),
        "unique_nonhub_explicit_anchor_count": len(unique_nonhub),
        "study_municipalities_explicitly_served": study_served,
        "study_municipalities_missing_explicit_stop": study_missing,
        "field_check_pending_anchor_count": len(field_check_pending),
        "field_check_pending_anchors": sorted(field_check_pending),
        "technical_label_anchor_count": len(technical_label_anchors),
        "technical_label_anchors": sorted(technical_label_anchors),
        "missing_anchor_metadata": sorted(missing_anchor_metadata),
        "routes": route_rows,
        "rt005_failure_reasons": failure_reasons,
        "passes_v3_territorial_guard": not failure_reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", required=True, type=Path)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--access-equity-source", required=True, type=Path)
    parser.add_argument("--structural-workflow", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    finalists = load_finalists(args.routes)
    if len(finalists) != 4:
        raise AssertionError(f"Expected exactly four current finalists, got {len(finalists)}")
    anchor_universe = load_anchor_universe(args.anchors)

    access_source = args.access_equity_source.read_text(encoding="utf-8")
    workflow_source = args.structural_workflow.read_text(encoding="utf-8")
    if "public_explicit_stop_anchor_count" not in access_source or "explicit_stop_anchors" not in access_source:
        raise AssertionError("Could not confirm Access Equity V2 explicit-stop semantics")
    if "--max-loop-intermediate-anchors 4" not in workflow_source:
        raise AssertionError("Could not confirm the four-intermediate-anchor structural search contract")

    audits = [audit_finalist(alias, finalists[alias], anchor_universe) for alias in sorted(finalists)]
    missing_calco = [row["finalist_alias"] for row in audits if "Calco" in row["study_municipalities_missing_explicit_stop"]]
    any_guard_failure = any(not row["passes_v3_territorial_guard"] for row in audits)
    if not any_guard_failure:
        raise AssertionError("RT-005 audit unexpectedly found no stop-pattern guard failure")

    payload = {
        "status": "PASS_RT005_FORMULATION_FAILURE_CONFIRMED",
        "decision_ready_current_finalists": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "audit_scope": "CURRENT_FOUR_FINALISTS_AS_NEGATIVE_REGRESSION_FIXTURE",
        "study_municipalities": list(STUDY_MUNICIPALITIES),
        "confirmed_upstream_contracts": {
            "structural_max_loop_intermediate_anchors": 4,
            "access_equity_uses_explicit_route_anchors_as_passenger_stop_set": True,
        },
        "current_finalist_count": len(audits),
        "finalists_missing_calco_explicit_stop": missing_calco,
        "all_current_finalists_missing_calco_explicit_stop": len(missing_calco) == len(audits),
        "finalist_audits": audits,
        "required_next_lineage": "PHASE2_CORRIDOR_AND_PASSENGER_STOP_PATTERN_V3",
        "lineage": {
            "finalist_route_structure": str(args.routes),
            "finalist_route_structure_sha256": sha256_path(args.routes),
            "routing_anchor_universe": str(args.anchors),
            "routing_anchor_universe_sha256": sha256_path(args.anchors),
            "access_equity_source": str(args.access_equity_source),
            "access_equity_source_sha256": sha256_path(args.access_equity_source),
            "structural_workflow": str(args.structural_workflow),
            "structural_workflow_sha256": sha256_path(args.structural_workflow),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
