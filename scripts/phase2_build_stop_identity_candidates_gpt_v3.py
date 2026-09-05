#!/usr/bin/env python3
"""Build conservative stop-identity candidate edges for audit.

Creates review evidence only. It never merges source records, assigns final
boarding_point_id values, finalizes stop places or promotes routing terminals.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

import pandas as pd

CORE_MUNICIPALITIES = {
    "Brivio", "Calco", "La Valletta Brianza", "Olgiate Molgora", "Santa Maria Hoè"
}


def _text(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _norm_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode("ascii")
    text = text.upper().replace("S.S.", "SS").replace("S.P.", "SP")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _name_similarity(a: str, b: str) -> float:
    na, nb = _norm_name(a), _norm_name(b)
    return SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _legacy_crossfeed_key(native_id: str) -> str:
    text = _text(native_id).upper()
    if re.fullmatch(r"3\d{5}", text):
        return text[-5:]
    if re.fullmatch(r"L\d{5}", text):
        return text[1:]
    return ""


def _asf_directional_pairs(asf: pd.DataFrame) -> pd.DataFrame:
    work = asf.copy()
    work["normalized_stop_name"] = work["source_stop_name"].map(_norm_name)
    rows: list[dict] = []
    pair_id = 0
    for (municipality, norm_name), group in work.groupby(
        ["physical_municipality_exact", "normalized_stop_name"], dropna=False, sort=True
    ):
        records = list(group.to_dict(orient="records"))
        if len(records) == 1:
            r = records[0]
            pair_id += 1
            rows.append({
                "pair_id": f"ASFDIR{pair_id:03d}",
                "physical_municipality_exact": municipality,
                "normalized_stop_name": norm_name,
                "source_record_a": r["master_source_record_id"],
                "source_record_b": "",
                "native_code_a": r["source_record_native_id"],
                "native_code_b": "",
                "name_a": r["source_stop_name"],
                "name_b": "",
                "distance_m": "",
                "same_operator_named_stop_place_status": "SINGLE_DIRECTIONAL_RECORD_ONLY",
                "boarding_point_identity_status": "SOURCE_RECORD_PRESERVED_NO_MERGE",
            })
            continue
        for a, b in combinations(records, 2):
            pair_id += 1
            distance = _haversine_m(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))
            rows.append({
                "pair_id": f"ASFDIR{pair_id:03d}",
                "physical_municipality_exact": municipality,
                "normalized_stop_name": norm_name,
                "source_record_a": a["master_source_record_id"],
                "source_record_b": b["master_source_record_id"],
                "native_code_a": a["source_record_native_id"],
                "native_code_b": b["source_record_native_id"],
                "name_a": a["source_stop_name"],
                "name_b": b["source_stop_name"],
                "distance_m": round(distance, 2),
                "same_operator_named_stop_place_status": "SAME_OPERATOR_NAMED_STOP_PLACE",
                "boarding_point_identity_status": "DISTINCT_DIRECTIONAL_SOURCE_RECORDS_NO_AUTO_MERGE",
            })
    return pd.DataFrame(rows)


def _asf_to_frozen_candidates(asf: pd.DataFrame, frozen: pd.DataFrame, radius_m: float, top_k: int) -> pd.DataFrame:
    rows: list[dict] = []
    for a in asf.to_dict(orient="records"):
        municipality = a["physical_municipality_exact"]
        local = frozen[frozen["physical_municipality_exact"].eq(municipality)]
        candidates: list[tuple[float, float, dict]] = []
        for f in local.to_dict(orient="records"):
            distance = _haversine_m(float(a["lat"]), float(a["lon"]), float(f["lat"]), float(f["lon"]))
            if distance <= radius_m:
                candidates.append((distance, _name_similarity(a["source_stop_name"], f["source_stop_name"]), f))
        candidates.sort(key=lambda item: (item[0], -item[1], item[2]["master_source_record_id"]))
        for rank, (distance, similarity, f) in enumerate(candidates[:top_k], start=1):
            if distance <= 15 and similarity >= 0.80:
                review_class = "VERY_CLOSE_NAME_ALIGNED_REVIEW"
            elif distance <= 30 and similarity >= 0.60:
                review_class = "CLOSE_PARTIAL_NAME_ALIGNMENT_REVIEW"
            elif distance <= 50:
                review_class = "CLOSE_GEOMETRY_IDENTITY_UNRESOLVED"
            elif distance <= 150:
                review_class = "SAME_LOCAL_AREA_REVIEW"
            else:
                review_class = "CORRIDOR_PROXIMITY_ONLY"
            rows.append({
                "asf_source_record": a["master_source_record_id"],
                "asf_code": a["source_record_native_id"],
                "asf_name": a["source_stop_name"],
                "physical_municipality_exact": municipality,
                "candidate_rank": rank,
                "frozen_source_record": f["master_source_record_id"],
                "frozen_native_id": f["source_record_native_id"],
                "frozen_name": f["source_stop_name"],
                "distance_m": round(distance, 2),
                "name_similarity": round(similarity, 4),
                "candidate_review_class": review_class,
                "identity_decision": "UNRESOLVED_NO_AUTO_MERGE",
            })
    return pd.DataFrame(rows)


def _frozen_crossfeed_aliases(frozen: pd.DataFrame) -> pd.DataFrame:
    work = frozen.copy()
    work["crossfeed_key"] = work["source_record_native_id"].map(_legacy_crossfeed_key)
    work = work[work["crossfeed_key"].ne("")]
    rows: list[dict] = []
    alias_id = 0
    for key, group in work.groupby("crossfeed_key", sort=True):
        numeric = group[group["source_record_native_id"].str.match(r"^3\d{5}$", na=False)]
        linee = group[group["source_record_native_id"].str.match(r"^L\d{5}$", na=False)]
        for a in numeric.to_dict(orient="records"):
            for b in linee.to_dict(orient="records"):
                alias_id += 1
                distance = _haversine_m(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))
                similarity = _name_similarity(a["source_stop_name"], b["source_stop_name"])
                same_municipality = a["physical_municipality_exact"] == b["physical_municipality_exact"]
                status = (
                    "STRONG_CROSS_FEED_SOURCE_ALIAS_CANDIDATE"
                    if distance <= 30 and similarity >= 0.85 and same_municipality
                    else "CROSS_FEED_ID_KEY_REVIEW_REQUIRED"
                )
                rows.append({
                    "alias_id": f"FALIAS{alias_id:03d}",
                    "crossfeed_key": key,
                    "source_record_a": a["master_source_record_id"],
                    "source_record_b": b["master_source_record_id"],
                    "native_id_a": a["source_record_native_id"],
                    "native_id_b": b["source_record_native_id"],
                    "name_a": a["source_stop_name"],
                    "name_b": b["source_stop_name"],
                    "municipality_a": a["physical_municipality_exact"],
                    "municipality_b": b["physical_municipality_exact"],
                    "distance_m": round(distance, 2),
                    "name_similarity": round(similarity, 4),
                    "alias_candidate_status": status,
                    "boarding_point_identity_decision": "NOT_FINALIZED",
                })
    return pd.DataFrame(rows)


def build(args: argparse.Namespace) -> None:
    master = pd.read_csv(args.master_municipalized, dtype=str)
    required = {
        "master_source_record_id", "source_family", "source_record_native_id", "source_stop_name",
        "lat", "lon", "physical_municipality_exact", "routing_terminal_eligibility_status",
    }
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Municipalized master missing columns: {sorted(missing)}")
    if not master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all():
        raise ValueError("Identity candidate builder must not receive selected routing terminals")

    core = master[master["physical_municipality_exact"].isin(CORE_MUNICIPALITIES)].copy()
    asf = core[core["source_family"].eq("ASF_OPERATOR_OTP")].copy()
    frozen = core[core["source_family"].eq("FROZEN_GTFS_REFERENCE")].copy()
    directional = _asf_directional_pairs(asf)
    nearest = _asf_to_frozen_candidates(asf, frozen, args.radius_m, args.top_k)
    aliases = _frozen_crossfeed_aliases(frozen)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    directional.to_csv(out / "asf_directional_pair_distances_gpt_v3.csv", index=False)
    nearest.to_csv(out / "asf_frozen_identity_candidates_gpt_v3.csv", index=False)
    aliases.to_csv(out / "frozen_crossfeed_alias_candidates_gpt_v3.csv", index=False)

    paired_rows = directional[directional["source_record_b"].fillna("").ne("")]
    single_rows = directional[directional["source_record_b"].fillna("").eq("")]
    validation = {
        "status": "PASS_IDENTITY_CANDIDATE_EDGE_BUILD",
        "core_source_records_count": int(len(core)),
        "asf_source_records_count": int(len(asf)),
        "frozen_core_source_records_count": int(len(frozen)),
        "asf_directional_pair_rows": int(len(paired_rows)),
        "asf_single_direction_named_place_rows": int(len(single_rows)),
        "asf_frozen_candidate_edges": int(len(nearest)),
        "frozen_crossfeed_alias_edges": int(len(aliases)),
        "strong_crossfeed_source_alias_candidates": int(
            aliases["alias_candidate_status"].eq("STRONG_CROSS_FEED_SOURCE_ALIAS_CANDIDATE").sum()
            if not aliases.empty else 0
        ),
        "boarding_point_merges_performed": 0,
        "stop_place_finalizations_performed": 0,
        "routing_terminal_selected_count": 0,
        "candidate_radius_m": float(args.radius_m),
        "top_k_per_asf_record": int(args.top_k),
        "epistemic_note": (
            "All outputs are candidate/review edges. Distance and name similarity nominate review only. "
            "Cross-feed aliases additionally require a shared numeric source-ID suffix, close geometry, compatible names and same exact municipality, but remain non-finalized."
        ),
    }
    (out / "stop_identity_candidate_validation_gpt_v3.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master-municipalized",
        default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/master_stop_source_records_municipalized_gpt_v3.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3",
    )
    parser.add_argument("--radius-m", type=float, default=500.0)
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
