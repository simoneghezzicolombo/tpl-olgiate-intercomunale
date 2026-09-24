#!/usr/bin/env python3
"""Materialise the Phase 2 structural scenario catalog from validated inputs.

The runner knows no project geography. The caller supplies:
- a hub anchor ID;
- an anchor-universe CSV produced by a validated Phase 2 workstream;
- a directed reduced path-matrix CSV derived from the frozen Gate D graph.

No live OSM request, random generation or legacy candidate-route output is used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_optimizer_core import PathLeg, ReducedPathMatrix, generate_structural_scenarios


ALLOWED_EVIDENCE_STATES = {
    "FACT",
    "FACT_OSM_OBSERVATION",
    "DERIVED",
    "ESTIMATE",
    "ASSUMPTION",
    "RECONSTRUCTED",
    "FIELD CHECK",
    "PROPOSED_STOP/FIELD_CHECK_PENDING",
}
FORBIDDEN_EVIDENCE_STATES = {"PLACEHOLDER", "INVALIDATED"}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_bool(value: str) -> bool:
    normalised = str(value).strip().lower()
    if normalised in {"1", "true", "yes", "y"}:
        return True
    if normalised in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def load_anchor_universe(path: Path) -> list[str]:
    """Load eligible anchor IDs from the Phase 2 anchor contract.

    Required columns:
    - anchor_id
    - evidence_status

    Optional column:
    - enabled (defaults to true)
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"anchor_id", "evidence_status"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"Anchor universe missing columns: {missing}")
        anchors: list[str] = []
        seen: set[str] = set()
        for line_no, row in enumerate(reader, start=2):
            anchor_id = str(row.get("anchor_id", "")).strip()
            status = str(row.get("evidence_status", "")).strip().upper()
            if not anchor_id:
                raise ValueError(f"Anchor universe line {line_no} has empty anchor_id")
            if status in FORBIDDEN_EVIDENCE_STATES:
                raise ValueError(f"Anchor {anchor_id} uses forbidden evidence state {status}")
            if status not in ALLOWED_EVIDENCE_STATES:
                raise ValueError(f"Anchor {anchor_id} has unsupported evidence state {status}")
            enabled = parse_bool(row.get("enabled", "true")) if "enabled" in fields else True
            if not enabled:
                continue
            if anchor_id in seen:
                raise ValueError(f"Duplicate enabled anchor_id: {anchor_id}")
            seen.add(anchor_id)
            anchors.append(anchor_id)
    if not anchors:
        raise ValueError("Anchor universe contains no enabled anchors")
    return sorted(anchors)


def load_reduced_path_matrix(path: Path) -> ReducedPathMatrix:
    """Load the directed path matrix contract.

    Required columns:
    origin,destination,distance_km,runtime_min,uncertainty
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"origin", "destination", "distance_km", "runtime_min", "uncertainty"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"Reduced path matrix missing columns: {missing}")
        legs: list[PathLeg] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                legs.append(
                    PathLeg(
                        origin=str(row["origin"]).strip(),
                        destination=str(row["destination"]).strip(),
                        distance_km=float(row["distance_km"]),
                        runtime_min=float(row["runtime_min"]),
                        uncertainty=str(row["uncertainty"]).strip().upper(),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid reduced path matrix line {line_no}: {exc}") from exc
    return ReducedPathMatrix(legs)


def write_catalog(path: Path, scenarios) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "scenario_id",
            "topology_family",
            "n_public_routes",
            "n_optional_extensions",
            "routes_json",
            "optional_extensions_json",
            "seed_name",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for scenario in scenarios:
            writer.writerow(
                {
                    "scenario_id": scenario.scenario_id,
                    "topology_family": scenario.family.value,
                    "n_public_routes": len(scenario.routes),
                    "n_optional_extensions": len(scenario.optional_extensions),
                    "routes_json": json.dumps(
                        [list(route.anchors) for route in scenario.routes],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "optional_extensions_json": json.dumps(
                        [list(route.anchors) for route in scenario.optional_extensions],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "seed_name": scenario.seed_name or "",
                }
            )


def write_validation(
    path: Path,
    *,
    hub: str,
    anchor_path: Path,
    matrix_path: Path,
    output_path: Path,
    anchors: list[str],
    scenarios,
    max_scenarios: int,
    max_loop_intermediate_anchors: int,
) -> None:
    family_counts: dict[str, int] = {}
    for scenario in scenarios:
        family_counts[scenario.family.value] = family_counts.get(scenario.family.value, 0) + 1
    payload = {
        "contract": "PHASE2_STRUCTURAL_SEARCH_V1",
        "hub_anchor_id": hub,
        "anchor_universe": str(anchor_path),
        "anchor_universe_sha256": sha256_path(anchor_path),
        "reduced_path_matrix": str(matrix_path),
        "reduced_path_matrix_sha256": sha256_path(matrix_path),
        "scenario_catalog": str(output_path),
        "scenario_catalog_sha256": sha256_path(output_path),
        "n_enabled_anchors": len(anchors),
        "n_generated_scenarios": len(scenarios),
        "family_counts": dict(sorted(family_counts.items())),
        "max_scenarios": max_scenarios,
        "max_loop_intermediate_anchors": max_loop_intermediate_anchors,
        "deterministic": True,
        "uses_live_osm": False,
        "uses_random_generation": False,
        "uses_legacy_candidate_routes": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub", required=True, help="Anchor ID of the Phase 2 interchange hub")
    parser.add_argument("--anchors", required=True, type=Path, help="Validated anchor-universe CSV")
    parser.add_argument("--path-matrix", required=True, type=Path, help="Directed reduced path-matrix CSV")
    parser.add_argument("--output", required=True, type=Path, help="Scenario catalog CSV to create")
    parser.add_argument("--validation", required=True, type=Path, help="Validation/provenance JSON to create")
    parser.add_argument("--max-scenarios", type=int, default=100_000)
    parser.add_argument("--max-loop-intermediate-anchors", type=int, default=4)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.anchors.is_file():
        raise FileNotFoundError(args.anchors)
    if not args.path_matrix.is_file():
        raise FileNotFoundError(args.path_matrix)
    anchors = load_anchor_universe(args.anchors)
    if args.hub not in anchors:
        raise ValueError(f"Hub {args.hub!r} is not an enabled anchor in {args.anchors}")
    matrix = load_reduced_path_matrix(args.path_matrix)
    scenarios = generate_structural_scenarios(
        hub=args.hub,
        anchors=anchors,
        matrix=matrix,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    if not scenarios:
        raise RuntimeError("Structural search generated no feasible scenario skeletons")
    write_catalog(args.output, scenarios)
    write_validation(
        args.validation,
        hub=args.hub,
        anchor_path=args.anchors,
        matrix_path=args.path_matrix,
        output_path=args.output,
        anchors=anchors,
        scenarios=scenarios,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    print(f"generated {len(scenarios)} deterministic structural scenarios -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
