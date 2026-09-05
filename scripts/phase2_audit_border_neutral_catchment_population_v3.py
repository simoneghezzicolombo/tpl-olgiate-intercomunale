#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import box

from src.phase2_border_neutral_catchment_population_v3 import (
    PopulationUnit,
    calibrate_envelope_cell_weights,
    discover_intersecting_municipality_codes,
    max_walk_distance_metres,
    split_discovered_municipalities,
    summarize_covered_population,
)


OUT = Path(
    "outputs/phase2/border_neutral_catchment_population_v3/"
    "border_neutral_catchment_population_v3_validation.json"
)


def main() -> None:
    core_codes = {"A", "B"}
    service_area = box(0, 0, 1000, 1000)
    municipalities = {
        "A": box(0, 0, 500, 1000),
        "B": box(500, 0, 1000, 1000),
        "EDGE": box(1500, 100, 2000, 900),
        "FAR": box(3000, 0, 3500, 1000),
    }
    buffer_m = max_walk_distance_metres()
    discovered = discover_intersecting_municipality_codes(
        service_area, municipalities, buffer_metres=buffer_m
    )
    split = split_discovered_municipalities(discovered, core_codes=core_codes)
    calibrated_fragment = calibrate_envelope_cell_weights(
        {"edge_1": 10.0, "edge_2": 20.0},
        official_population_total=200.0,
        full_municipality_worldpop_raw_sum=100.0,
    )
    summary = summarize_covered_population(
        ["a1", "edge_1", "edge_1", "edge_2"],
        population_units=[
            PopulationUnit("a1", "A", 100.0),
            PopulationUnit("b1", "B", 80.0),
            PopulationUnit("edge_1", "EDGE", calibrated_fragment["edge_1"]),
            PopulationUnit("edge_2", "EDGE", calibrated_fragment["edge_2"]),
        ],
        core_codes=core_codes,
    )

    checks = {
        "default_buffer_is_960m": abs(buffer_m - 960.0) < 1e-9,
        "geometry_discovers_edge_without_manual_neighbor_list": discovered
        == ("A", "B", "EDGE"),
        "far_municipality_excluded": "FAR" not in discovered,
        "core_set_preserved": split["core"] == ("A", "B"),
        "external_set_separate": split["external"] == ("EDGE",),
        "fragment_not_inflated_to_full_municipality_total": abs(
            sum(calibrated_fragment.values()) - 60.0
        )
        < 1e-9,
        "coverage_deduplicates_population_units": summary.external_covered_units == 2,
        "core_population_separate": abs(summary.core_covered_population - 100.0) < 1e-9,
        "external_spillover_separate": abs(summary.external_spillover_population - 60.0)
        < 1e-9,
        "total_is_core_plus_external": abs(summary.total_catchment_population - 160.0)
        < 1e-9,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": "RT016_V3",
        "verdict": verdict,
        "checks": checks,
        "controlled_fixture": {
            "buffer_metres": buffer_m,
            "discovered_municipalities": list(discovered),
            "external_municipalities": list(split["external"]),
            "calibrated_external_fragment_population": sum(calibrated_fragment.values()),
            "core_covered_population": summary.core_covered_population,
            "external_spillover_population": summary.external_spillover_population,
            "total_catchment_population": summary.total_catchment_population,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
