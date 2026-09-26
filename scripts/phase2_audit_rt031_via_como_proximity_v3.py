"""Geometric, non-operational proximity screen for the Via Como stop place."""

import argparse
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

from scripts.phase2_audit_rt031_south_road_probe_v3 import digest


STOP = "ASF::SANTA_MARIA_HOE_VIA_COMO"
SWAPPED_IDS = ["FROZEN::300879", "ASF::PEREGO_VIA_STATALE_79"]


def build(paths):
    baseline = json.loads(paths["baseline"].read_text(encoding="utf-8"))
    swap = json.loads(paths["swap"].read_text(encoding="utf-8"))
    audit = json.loads(paths["road_audit"].read_text(encoding="utf-8"))
    if (baseline["name"] != "RT031_LINE8_INCLUSIVE_MODELED_ROAD_SHAPE_V3"
            or swap["name"] != "RT031_LINE8_WEST_WAYPOINT_SWAP_MODELED_ROAD_SHAPE_V3"
            or audit["contract"] != "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3"):
        raise ValueError("route geometry or audit contract drift")
    option = next(o for o in audit["options"]
                  if o["edit"] == "SWAP_ADJACENT_EXISTING_WAYPOINTS"
                  and o["wing"] == "west"
                  and o["affected_waypoint_ids"] == SWAPPED_IDS)
    if option["existing_stop_ids_lost_both_directions"] != [STOP]:
        raise ValueError("Via Como is not the single lost encounter")
    stop_features = [f for f in baseline["features"]
                     if f["properties"].get("stop_place_id") == STOP]
    if len(stop_features) != 1:
        raise ValueError("Via Como point absent or ambiguous")
    lon, lat = stop_features[0]["geometry"]["coordinates"]
    forward = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    backward = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
    point = transform(forward.transform, Point(lon, lat))
    comparisons = {}
    features = [stop_features[0]]
    for geometry_name, source in (("baseline", baseline), ("west_swap", swap)):
        lines = [f for f in source["features"] if f["geometry"]["type"] == "LineString"]
        if len(lines) != 2:
            raise ValueError("expected both route directions")
        comparisons[geometry_name] = {}
        for feature in lines:
            direction = feature["properties"]["traversal"]
            line = transform(forward.transform,
                             LineString(feature["geometry"]["coordinates"]))
            nearest = line.interpolate(line.project(point))
            near_lon, near_lat = backward.transform(nearest.x, nearest.y)
            near_coord = [round(near_lon, 8), round(near_lat, 8)]
            distance = round(point.distance(nearest), 3)
            comparisons[geometry_name][direction] = {
                "planar_straight_line_distance_m": distance,
                "nearest_route_point_lon_lat": near_coord,
            }
            if geometry_name == "west_swap":
                features.append({
                    "type": "Feature",
                    "properties": {"feature_type": "NEAREST_MODELED_ROAD_POINT_NOT_STOP_SITE",
                                   "traversal": direction, "straight_line_distance_m": distance},
                    "geometry": {"type": "Point", "coordinates": near_coord},
                })
                features.append({
                    "type": "Feature",
                    "properties": {"feature_type": "STRAIGHT_LINE_SEPARATION_NOT_WALKING_PATH",
                                   "traversal": direction, "distance_m": distance},
                    "geometry": {"type": "LineString",
                                 "coordinates": [[lon, lat], near_coord]},
                })
    if max(r["planar_straight_line_distance_m"]
           for r in comparisons["baseline"].values()) > 5:
        raise ValueError("baseline Via Como stop too far from old modeled route")
    result = {
        "contract": "RT031_VIA_COMO_STOP_TO_WEST_SWAP_ROAD_PROXIMITY_V3",
        "status": "NON_DECISIONAL_STRAIGHT_LINE_GEOMETRY_ONLY",
        "stop_place_id": STOP,
        "stop_place_lon_lat": [lon, lat],
        "metric_crs": "EPSG:32632",
        "comparisons": comparisons,
        "source_sha256": {key: digest(paths[key], True) for key in paths},
        "does_not_establish": ["same usable stop location", "pedestrian connection",
                               "correct side of road in both directions",
                               "safe boarding and bus stopping", "road legality for full vehicle",
                               "retained 5-minute walking access", "passenger service event"],
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }
    geojson = {
        "type": "FeatureCollection",
        "name": "RT031_VIA_COMO_WEST_SWAP_PROXIMITY_V3",
        "properties": {"status": result["status"],
                       "source_sha256": result["source_sha256"],
                       "network_selected": False},
        "features": features,
    }
    return result, geojson


def main(paths, output, geojson_output):
    result, geojson = build(paths)
    for path, data in ((output, result), (geojson_output, geojson)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("baseline", "swap", "road_audit", "output", "geojson_output"):
        parser.add_argument("--" + key.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in ("baseline", "swap", "road_audit")},
         args.output, args.geojson_output)
