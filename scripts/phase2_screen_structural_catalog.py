#!/usr/bin/env python3
"""Screen a Phase 2 structural catalog without selecting or ranking networks."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_structural_search import load_reduced_path_matrix
from src.phase2_structural_screening import AnchorMeta, summarise_scenario_structure


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean {value!r}")


def load_anchor_meta(path: Path) -> dict[str, AnchorMeta]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"anchor_id", "source_kind"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"Anchor universe missing columns: {missing}")
        result: dict[str, AnchorMeta] = {}
        for line_no, row in enumerate(reader, start=2):
            if "enabled" in fields and not parse_bool(row.get("enabled", "true")):
                continue
            anchor_id = str(row.get("anchor_id", "")).strip()
            source_kind = str(row.get("source_kind", "")).strip().upper()
            if anchor_id in result:
                raise ValueError(f"Duplicate enabled anchor_id at line {line_no}: {anchor_id}")
            result[anchor_id] = AnchorMeta(anchor_id=anchor_id, source_kind=source_kind)
    if not result:
        raise ValueError("Anchor universe contains no enabled anchors")
    return result


def parse_routes(raw: str, *, field: str, line_no: int) -> list[list[str]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Catalog line {line_no} has invalid {field} JSON") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Catalog line {line_no} {field} must be a JSON list")
    routes: list[list[str]] = []
    for index, route in enumerate(payload):
        if not isinstance(route, list) or len(route) < 2:
            raise ValueError(f"Catalog line {line_no} {field}[{index}] is not a route")
        anchors = [str(anchor).strip() for anchor in route]
        if any(not anchor for anchor in anchors):
            raise ValueError(f"Catalog line {line_no} {field}[{index}] has empty anchor")
        routes.append(anchors)
    return routes


def screen_catalog(
    *,
    catalog_path: Path,
    matrix_path: Path,
    anchor_path: Path,
    output_path: Path,
    abs_tol_km: float,
    rel_tol: float,
) -> tuple[int, dict[str, int], int]:
    if not math.isfinite(abs_tol_km) or abs_tol_km < 0:
        raise ValueError("on-path absolute tolerance must be finite and non-negative")
    if not math.isfinite(rel_tol) or rel_tol < 0:
        raise ValueError("on-path relative tolerance must be finite and non-negative")
    matrix = load_reduced_path_matrix(matrix_path)
    anchor_meta = load_anchor_meta(anchor_path)
    leg_cache: dict[tuple[str, str], frozenset[str]] = {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    family_counts: dict[str, int] = {}
    row_count = 0
    seen_ids: set[str] = set()
    writer = None
    output_handle = output_path.open("w", encoding="utf-8", newline="")
    try:
        with catalog_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fields = set(reader.fieldnames or [])
            required = {"scenario_id", "topology_family", "routes_json", "optional_extensions_json"}
            missing = sorted(required - fields)
            if missing:
                raise ValueError(f"Scenario catalog missing columns: {missing}")
            for line_no, row in enumerate(reader, start=2):
                scenario_id = str(row.get("scenario_id", "")).strip()
                family = str(row.get("topology_family", "")).strip()
                if not scenario_id or not family:
                    raise ValueError(f"Catalog line {line_no} has empty scenario/family")
                if scenario_id in seen_ids:
                    raise ValueError(f"Duplicate scenario_id {scenario_id!r}")
                seen_ids.add(scenario_id)
                routes = parse_routes(row["routes_json"], field="routes_json", line_no=line_no)
                extensions = parse_routes(
                    row["optional_extensions_json"],
                    field="optional_extensions_json",
                    line_no=line_no,
                )
                used_anchors = {anchor for route in routes + extensions for anchor in route}
                missing_anchors = sorted(used_anchors - set(anchor_meta))
                if missing_anchors:
                    raise ValueError(
                        f"Catalog line {line_no} references anchors absent from universe: {missing_anchors[:5]}"
                    )
                metrics = summarise_scenario_structure(
                    matrix,
                    routes=routes,
                    optional_extensions=extensions,
                    anchor_meta=anchor_meta,
                    abs_tol_km=abs_tol_km,
                    rel_tol=rel_tol,
                    leg_cache=leg_cache,
                )
                out = {
                    "scenario_id": scenario_id,
                    "topology_family": family,
                    "seed_name": str(row.get("seed_name", "")).strip(),
                    **metrics,
                }
                if writer is None:
                    writer = csv.DictWriter(output_handle, fieldnames=list(out), lineterminator="\n")
                    writer.writeheader()
                writer.writerow(out)
                row_count += 1
                family_counts[family] = family_counts.get(family, 0) + 1
    finally:
        output_handle.close()
    if row_count == 0:
        raise ValueError("Scenario catalog contains no scenarios")
    return row_count, dict(sorted(family_counts.items())), len(leg_cache)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--path-matrix", required=True, type=Path)
    parser.add_argument("--anchor-universe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--on-path-abs-tol-km", required=True, type=float)
    parser.add_argument("--on-path-rel-tol", required=True, type=float)
    parser.add_argument("--evidence-label", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for path in (args.catalog, args.path_matrix, args.anchor_universe):
        if not path.is_file():
            raise FileNotFoundError(path)
    rows, family_counts, cached_legs = screen_catalog(
        catalog_path=args.catalog,
        matrix_path=args.path_matrix,
        anchor_path=args.anchor_universe,
        output_path=args.output,
        abs_tol_km=args.on_path_abs_tol_km,
        rel_tol=args.on_path_rel_tol,
    )
    payload = {
        "status": "PASS",
        "contract": "PHASE2_TOPOLOGY_NEUTRAL_STRUCTURAL_SCREENING_V1",
        "evidence_label": args.evidence_label,
        "scenario_count": rows,
        "family_counts": family_counts,
        "unique_directed_scenario_legs_screened": cached_legs,
        "on_path_test": "d(A,C)+d(C,B) approximately equals d(A,B)",
        "on_path_abs_tol_km": args.on_path_abs_tol_km,
        "on_path_rel_tol": args.on_path_rel_tol,
        "catalog_sha256": sha256_path(args.catalog),
        "path_matrix_sha256": sha256_path(args.path_matrix),
        "anchor_universe_sha256": sha256_path(args.anchor_universe),
        "screening_output_sha256": sha256_path(args.output),
        "uses_live_osm": False,
        "uses_random_generation": False,
        "uses_legacy_candidate_routes": False,
        "selects_topology": False,
        "ranks_topology_family": False,
        "selects_stops": False,
        "annualises_service": False,
        "chooses_service_policy": False,
        "epistemic_note": (
            "These are structural skeleton metrics only. Distances/runtimes are sums of directed "
            "reduced-path legs exactly as represented by each catalog route. Open skeletons are not "
            "silently closed into cycles. Intercepted stops are shortest-path structural potentials, "
            "not operational stop calls or recommendations."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"screened {rows} scenarios across {cached_legs} unique directed legs -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
