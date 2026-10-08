"""Build the presentation asset from confirmed sources; never select a design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "outputs/phase2/rt031_line8_local_shortcuts_v3/"
SOURCES = {
    "design": BASE + "caller_confirmed_design_handoff_20261001.json",
    "calendar": BASE + "caller_confirmed_weekday_calendar_2027.json",
    "geometry": BASE + "calco_centre_adopted_design.geojson",
}
ASSET = ROOT / "assets/nodo8-proposal.json"


def source_digest(path: Path) -> str:
    """Match Git's source bytes across LF and Windows CRLF checkouts."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

MUNICIPALITIES = [
    {"code": "97058", "name": "Olgiate Molgora"},
    {"code": "97012", "name": "Calco"},
    {"code": "97010", "name": "Brivio"},
    {"code": "97074", "name": "Santa Maria Hoè"},
    {"code": "97092", "name": "La Valletta Brianza"},
]


def build_data(root: Path = ROOT) -> dict:
    loaded = {key: json.loads((root / path).read_text(encoding="utf-8")) for key, path in SOURCES.items()}
    design, calendar, geo = (loaded[key] for key in ("design", "calendar", "geometry"))
    flags = [
        "public_operating_timetable_authorised", "network_selected",
        "primary_selection_authorised", "runner_up_selection_authorised",
        "physical_boarding_authorised", "funding_secured",
    ]
    if any(design[key] is not False or calendar[key] is not False for key in flags):
        raise ValueError("Authority changed: review showcase copy, do not imply authorisation.")
    if design["all_trips_same_complete_path"] is not True or len(design["full_trips"]) != 16:
        raise ValueError("This showcase only describes the confirmed 16 uniform complete trips.")
    sites = design["design_stop_register"]
    if len(sites) != 27 or sum(site["proposed_new_site"] for site in sites) != 4:
        raise ValueError("Site register changed: review public copy.")
    if calendar["service_year"] != 2027 or calendar["weekday_base_day_count_before_local_exceptions"] != 254:
        raise ValueError("Calendar changed: review public copy.")
    routes = [{"wing": f["properties"]["wing"], "coordinates": f["geometry"]["coordinates"]}
              for f in geo["features"] if f["geometry"]["type"] == "LineString"]
    if {route["wing"] for route in routes} != {"east_A", "west_B"} or len(routes) != 2:
        raise ValueError("Expected the two confirmed ordered wing geometries.")
    peak_departures = {minute for bank in design["h30_banks"]
                       if bank["wing"] == "east_A" for minute in bank["bus_departures_min"]}
    trips = [{"number": i + 1, **trip,
              "return_fs_min": trip["second_fs_min"] + design["nominal_wing_duration_min"]["west_B"],
              "peak_bank": trip["first_fs_min"] in peak_departures}
             for i, trip in enumerate(design["full_trips"])]
    return {
        "contract": "nodo8_showcase_v1",
        "brand": {"name": "Nodo8", "official_name": design["public_route_name"], "working_name": True},
        "as_of": "2026-10-07",
        "sources": {key: {"path": path, "sha256": source_digest(root / path),
                          "sha256_semantics": "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF"}
                    for key, path in SOURCES.items()},
        "authority": {**{key: design[key] for key in flags},
                      **{key: design[key] for key in [
                          "decision_budget_km", "uncertainty_band_min",
                          "missed_connection_probability", "demand_weighted_gjt_improvement_min"]}},
        "calendar": {key: calendar[key] for key in [
            "service_year", "weekday_base_day_count_before_local_exceptions",
            "weekday_base_complete_trip_count", "weekday_base_commercial_km",
            "reference_published_pdb_annual_km", "saturday_service_policy_adopted",
            "annual_noncommercial_km", "full_annual_operating_cost"]},
        "complete_path_distance_m": design["complete_path_distance_m"],
        "municipalities": MUNICIPALITIES,
        "coverage": design["coverage_percent"],
        "coverage_semantics": design["coverage_semantics"],
        "trips": trips, "sites": sites, "routes": routes,
    }


def serialise(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if checked-in presentation data differ.")
    args = parser.parse_args()
    expected = serialise(build_data())
    if args.check:
        if not ASSET.exists() or ASSET.read_text(encoding="utf-8") != expected:
            raise SystemExit("Presentation data stale. Run python scripts/build_nodo8_website_data.py")
        print("Nodo8 showcase matches all three confirmed sources.")
    else:
        ASSET.parent.mkdir(parents=True, exist_ok=True)
        ASSET.write_text(expected, encoding="utf-8", newline="\n")
        print("Built assets/nodo8-proposal.json from confirmed sources.")


if __name__ == "__main__":
    main()
