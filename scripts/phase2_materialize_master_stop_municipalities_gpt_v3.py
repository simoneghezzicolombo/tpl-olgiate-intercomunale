#!/usr/bin/env python3
"""Materialize strict physical municipality membership for master stop source records.

This step uses only point-in-polygon containment against the frozen ISTAT 2026
core-municipality GeoJSON. It does not infer municipality from stop names, GTFS
context labels, route assignment, nearest road, or legacy PRO_COM_T.

Rows outside the five core municipality polygons are retained and explicitly marked
OUTSIDE_CORE rather than being dropped or reassigned. This preserves provenance and
prevents context-universe rows from contaminating territorial stop counts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


CORE_CODE_TO_MUNICIPALITY = {
    "097010": "Brivio",
    "097012": "Calco",
    "097058": "Olgiate Molgora",
    "097074": "Santa Maria Hoè",
    "097092": "La Valletta Brianza",
}
CORE_MUNICIPALITIES = set(CORE_CODE_TO_MUNICIPALITY.values())
OUTSIDE_CORE = "OUTSIDE_CORE"


def _point_on_segment(x: float, y: float, a: list[float], b: list[float], eps: float = 1e-12) -> bool:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return (
        min(ax, bx) - eps <= x <= max(ax, bx) + eps
        and min(ay, by) - eps <= y <= max(ay, by) + eps
    )


def _ring_contains(x: float, y: float, ring: list[list[float]]) -> bool:
    if len(ring) < 4:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        a = ring[j]
        b = ring[i]
        if _point_on_segment(x, y, a, b):
            return True
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        intersects = ((ay > y) != (by > y)) and (
            x < (bx - ax) * (y - ay) / (by - ay) + ax
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _polygon_contains(x: float, y: float, rings: list[list[list[float]]]) -> bool:
    if not rings or not _ring_contains(x, y, rings[0]):
        return False
    # A point in an interior ring is outside the polygon. Boundary is treated as inside
    # by _ring_contains; exact administrative-boundary points are expected to be rare and
    # are caught by the multi-match guard if shared by two municipalities.
    return not any(_ring_contains(x, y, hole) for hole in rings[1:])


def _geometry_contains(x: float, y: float, geometry: dict) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return _polygon_contains(x, y, coords)
    if gtype == "MultiPolygon":
        return any(_polygon_contains(x, y, polygon) for polygon in coords)
    raise ValueError(f"Unsupported boundary geometry type: {gtype!r}")


def _normalise_pro_com_t(props: dict) -> str:
    raw = props.get("PRO_COM_T")
    if raw is None:
        raw = props.get("PRO_COM")
    if raw is None:
        return ""
    text = str(raw).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def _load_boundaries(path: Path) -> list[tuple[str, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    boundaries: list[tuple[str, dict]] = []
    found_codes: set[str] = set()
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        code = _normalise_pro_com_t(props)
        municipality = CORE_CODE_TO_MUNICIPALITY.get(code)
        if municipality is None:
            continue
        found_codes.add(code)
        boundaries.append((municipality, feature["geometry"]))
    expected_codes = set(CORE_CODE_TO_MUNICIPALITY)
    if found_codes != expected_codes:
        raise ValueError(
            "Boundary file must contain exactly the five core municipality ISTAT codes; "
            f"found={sorted(found_codes)} expected={sorted(expected_codes)}"
        )
    return boundaries


def _assign_municipality(lat: float, lon: float, boundaries: list[tuple[str, dict]]) -> str:
    matches = [name for name, geometry in boundaries if _geometry_contains(lon, lat, geometry)]
    if len(matches) > 1:
        raise ValueError(
            f"Point ({lat:.8f}, {lon:.8f}) matched multiple core municipalities: {matches}"
        )
    return matches[0] if matches else OUTSIDE_CORE


def _comparison_status(reported: str, exact: str) -> str:
    reported = reported.strip()
    if exact == OUTSIDE_CORE:
        if reported:
            return "REPORTED_CONTEXT_BUT_PHYSICALLY_OUTSIDE_CORE"
        return "PHYSICALLY_OUTSIDE_CORE_NO_REPORTED_MUNICIPALITY"
    if not reported:
        return "PHYSICAL_CORE_MUNICIPALITY_WITHOUT_REPORTED_VALUE"
    if reported == exact:
        return "AGREES_WITH_PHYSICAL_CONTAINMENT"
    return "REPORTED_MUNICIPALITY_CONFLICTS_WITH_PHYSICAL_CONTAINMENT"


def materialize(args: argparse.Namespace) -> None:
    master = pd.read_csv(args.master_source_records, dtype=str)
    required = {
        "master_source_record_id",
        "source_family",
        "source_record_native_id",
        "source_stop_name",
        "lat",
        "lon",
        "municipality_reported",
        "routing_terminal_eligibility_status",
    }
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Master source inventory missing columns: {sorted(missing)}")

    boundaries = _load_boundaries(Path(args.boundaries))

    exact: list[str] = []
    comparison: list[str] = []
    for row in master.itertuples(index=False):
        municipality = _assign_municipality(float(row.lat), float(row.lon), boundaries)
        exact.append(municipality)
        reported = "" if pd.isna(row.municipality_reported) else str(row.municipality_reported).strip()
        comparison.append(_comparison_status(reported, municipality))

    result = master.copy()
    result["physical_municipality_exact"] = exact
    result["municipality_comparison_status"] = comparison
    result["municipality_assignment_method"] = "ISTAT_2026_EXACT_POINT_IN_POLYGON"

    if result["physical_municipality_exact"].isna().any():
        raise ValueError("Municipality materialization left null exact municipalities")
    if not result["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all():
        raise ValueError("Municipality materialization must not select routing terminals")

    # The ASF evidence layer was already polygon-filtered. Recomputing containment here
    # independently must agree exactly with its reported municipality.
    asf = result[result["source_family"].eq("ASF_OPERATOR_OTP")]
    asf_conflicts = asf[
        ~asf["municipality_comparison_status"].eq("AGREES_WITH_PHYSICAL_CONTAINMENT")
    ]
    if not asf_conflicts.empty:
        cols = [
            "master_source_record_id",
            "source_stop_name",
            "municipality_reported",
            "physical_municipality_exact",
        ]
        raise ValueError(
            "ASF polygon evidence disagrees with independent containment: "
            + asf_conflicts[cols].to_dict(orient="records").__repr__()
        )

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "master_stop_source_records_municipalized_gpt_v3.csv", index=False)

    counts = (
        result.groupby(["physical_municipality_exact", "source_family"], dropna=False)
        .size()
        .rename("source_records")
        .reset_index()
        .sort_values(["physical_municipality_exact", "source_family"])
    )
    counts.to_csv(out / "master_stop_municipality_counts_gpt_v3.csv", index=False)

    disagreements = result[
        ~result["municipality_comparison_status"].eq("AGREES_WITH_PHYSICAL_CONTAINMENT")
    ].copy()
    disagreements.to_csv(out / "master_stop_municipality_review_gpt_v3.csv", index=False)

    validation = {
        "status": "PASS_EXACT_CORE_MUNICIPALITY_MATERIALIZATION",
        "source_records_count": int(len(result)),
        "core_polygon_assigned_count": int(result["physical_municipality_exact"].isin(CORE_MUNICIPALITIES).sum()),
        "outside_core_count": int(result["physical_municipality_exact"].eq(OUTSIDE_CORE).sum()),
        "reported_vs_physical_nonagreement_count": int(len(disagreements)),
        "asf_containment_conflict_count": int(len(asf_conflicts)),
        "assignment_method": "ISTAT_2026_EXACT_POINT_IN_POLYGON",
        "boundary_source": str(args.boundaries),
        "boundary_identity_key": "ISTAT_PRO_COM_T",
        "routing_terminal_selected_count": int(
            (~result["routing_terminal_eligibility_status"].eq("NOT_EVALUATED")).sum()
        ),
        "epistemic_note": (
            "OUTSIDE_CORE means outside the five frozen core ISTAT polygons, not an inferred exact external municipality. "
            "Boundary labels are canonicalized from stable ISTAT PRO_COM_T codes so text-encoding defects cannot change identity. "
            "No stop-name or nearest-place heuristic is used."
        ),
    }
    (out / "master_stop_municipality_validation_gpt_v3.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master-source-records",
        default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/master_stop_source_records_gpt_v3.csv",
    )
    parser.add_argument(
        "--boundaries",
        default="data/raw/boundaries/comuni_core_istat_2026.geojson",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3",
    )
    return parser.parse_args()


if __name__ == "__main__":
    materialize(parse_args())
