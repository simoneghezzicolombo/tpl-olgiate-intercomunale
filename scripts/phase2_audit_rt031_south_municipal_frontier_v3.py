"""Non-decisional south-Olgiate walking-access screen of the pinned 736 profiles."""

import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from shapely.geometry import Point, shape


EXPECTED = {
    "profiles": "03105f27fa3b979fb02e84da9ccdaad42134b9b3c6d1123792ba190e93ffe72a",
    "matrix": "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1",
    "population": "edba328d0214bec3a17357d2f21aba316b7ce4596b8ef47dad0c0ac92e45cd54",
    "area": "c30458ecdfe5a9671e8278d1f5d69d2f8a5360fb9ab29ba3017c07168c73f0ba",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(numerator, denominator):
    return str(Fraction(numerator) / Fraction(denominator))


def main(paths, output):
    for label, path in paths.items():
        if sha256(path) != EXPECTED[label]:
            raise ValueError(f"pinned {label} source drift")
    profiles_source = json.loads(paths["profiles"].read_text(encoding="utf-8"))
    profiles = profiles_source["profiles"]
    if (len(profiles) != 736 or profiles_source["network_selected"] is not False
            or profiles_source["primary_selection_authorised"] is not False):
        raise ValueError("typed frontier contract drift")
    area_source = json.loads(paths["area"].read_text(encoding="utf-8"))
    if area_source["bus_route_to_candidate_certified"] is not False:
        raise ValueError("area route-status drift")
    polygons = {name: shape(area["geometry"])
                for name, area in area_source["areas"].items()}
    with paths["population"].open(encoding="utf-8", newline="") as stream:
        population = {row["unit_id"]: row for row in csv.DictReader(stream)}
    eligible = {
        name: {unit_id: Decimal(row["population_weight_2025"])
               for unit_id, row in population.items()
               if row["population_scope"] == "core"
               and row["municipality_code"] == "097058"
               and polygon.covers(Point(float(row["lon"]), float(row["lat"])))}
        for name, polygon in polygons.items()
    }
    if any(len(weights) != area_source["areas"][name]["unit_count"]
           for name, weights in eligible.items()):
        raise ValueError("area population membership drift")
    stops = set().union(*(set(p["available_stop_ids"]) for p in profiles))
    if "P2V2S_0031" in stops:
        raise ValueError("southern proposed stop unexpectedly in frontier")
    reachable = {stop: {threshold: set() for threshold in (5, 8, 10)}
                 for stop in stops}
    observed_stops = set()
    units = set().union(*(set(group) for group in eligible.values()))
    with paths["matrix"].open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            stop, unit = row["stop_place_id"], row["population_unit_id"]
            if stop not in reachable or unit not in units:
                continue
            observed_stops.add(stop)
            if row["reachability_status"] != "REACHABLE":
                continue
            minutes = Decimal(row["walk_time_min"])
            for threshold in (5, 8, 10):
                if minutes <= threshold:
                    reachable[stop][threshold].add(unit)
    if observed_stops != stops:
        raise ValueError("profile stop missing from RT028 walking matrix")
    result = {}
    for name, weights in eligible.items():
        denominator = sum(weights.values(), Decimal(0))
        observations = []
        for profile in profiles:
            access = {}
            for threshold in (5, 8, 10):
                reached = set().union(*(reachable[stop][threshold]
                                        for stop in profile["available_stop_ids"]))
                numerator = sum((weights[unit] for unit in reached if unit in weights), Decimal(0))
                access[str(threshold)] = ratio(numerator, denominator)
            observations.append({"profile_id": profile["profile_id"],
                                 "walk_access": access})
        ranked = sorted(observations,
                        key=lambda row: Fraction(row["walk_access"]["10"]),
                        reverse=True)
        best = ranked[0]["walk_access"]["10"]
        result[name] = {
            "profile_count": len(observations),
            "unit_count": len(weights),
            "modelled_population_weight": str(denominator),
            "best_10min_walk_access": best,
            "best_10min_profile_count": sum(
                row["walk_access"]["10"] == best for row in observations),
            "example_best_profile_id": ranked[0]["profile_id"],
            "worst_10min_walk_access": ranked[-1]["walk_access"]["10"],
            "profiles_reaching_80pct_10min": sum(
                Fraction(row["walk_access"]["10"]) >= Fraction(4, 5)
                for row in observations),
            "profiles_reaching_85pct_10min": sum(
                Fraction(row["walk_access"]["10"]) >= Fraction(17, 20)
                for row in observations),
        }
    payload = {
        "contract": "RT031_SOUTH_MUNICIPAL_FRONTIER_WALK_ACCESS_V3",
        "status": "NON_DECISIONAL_PROVISIONAL_AREA_STOP_SET_SCREEN",
        "input_sha256": EXPECTED,
        "areas": result,
        "metric_semantics": "modelled population share within provisional area with <=10 min graph walk to any profile stop identity; not a served passenger journey",
        "provisional_area_not_caller_polygon": True,
        "new_southern_stop_in_profile_domain": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for label in EXPECTED:
        parser.add_argument(f"--{label}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main({label: getattr(args, label) for label in EXPECTED}, args.output)
