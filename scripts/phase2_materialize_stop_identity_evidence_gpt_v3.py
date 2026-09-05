#!/usr/bin/env python3
"""Materialize defensible stop identity evidence without physical-point conflation.

This layer intentionally separates two safe statements from the harder boarding-point
question:

1. source_alias_group_id: cross-feed source records that have a strong shared database
   key + compatible name + close geometry + same exact municipality may be grouped as
   representations of the same *source entity*. This is not a boarding-point merge.
2. operator_named_stop_place_id: ASF directional records sharing the same normalized
   operator stop name and exact municipality are grouped as one operator-named stop
   place. Directional source records remain distinct boarding-point candidates.

No final cross-operator stop_place_id and no final boarding_point_id are assigned here.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


def _text(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return text or "UNNAMED"


def _source_singleton_group(row: pd.Series) -> str:
    return f"SAG_SINGLE::{_slug(row['source_family'])}::{_slug(row['source_record_native_id'])}"


def materialize(args: argparse.Namespace) -> None:
    master = pd.read_csv(args.master_municipalized, dtype=str)
    directional = pd.read_csv(args.asf_directional_pairs, dtype=str)
    aliases = pd.read_csv(args.frozen_alias_candidates, dtype=str)

    required_master = {
        "master_source_record_id", "source_family", "source_record_native_id",
        "physical_municipality_exact", "boarding_point_id_candidate",
        "routing_terminal_eligibility_status",
    }
    missing = required_master - set(master.columns)
    if missing:
        raise ValueError(f"Municipalized master missing columns: {sorted(missing)}")
    if not master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all():
        raise ValueError("Identity evidence materializer cannot receive selected routing terminals")

    result = master.copy()
    result["source_alias_group_id"] = result.apply(_source_singleton_group, axis=1)
    result["source_alias_group_status"] = "SOURCE_SINGLETON_NO_ALIAS_DECISION"
    result["source_alias_group_epistemic_status"] = "FACT_SOURCE_RECORD_SINGLETON"
    result["operator_named_stop_place_id"] = ""
    result["operator_named_stop_place_status"] = "NOT_APPLICABLE_OR_NOT_MATERIALIZED"
    result["final_boarding_point_id"] = ""
    result["final_stop_place_id"] = ""

    # Strong cross-feed aliases are grouped only at source-entity level. Their physical
    # boarding identity remains explicitly unresolved.
    strong = aliases[aliases["alias_candidate_status"].eq("STRONG_CROSS_FEED_SOURCE_ALIAS_CANDIDATE")].copy()
    member_to_alias: dict[str, str] = {}
    for row in strong.itertuples(index=False):
        group_id = f"SAG_FROZEN_XFEED::{row.crossfeed_key}"
        for member in (row.source_record_a, row.source_record_b):
            if member in member_to_alias and member_to_alias[member] != group_id:
                raise ValueError(f"Source record {member} assigned to multiple source alias groups")
            member_to_alias[member] = group_id
    for member, group_id in member_to_alias.items():
        mask = result["master_source_record_id"].eq(member)
        if mask.sum() != 1:
            raise ValueError(f"Alias member not uniquely found in master: {member}")
        result.loc[mask, "source_alias_group_id"] = group_id
        result.loc[mask, "source_alias_group_status"] = "DERIVED_STRONG_CROSS_FEED_SOURCE_ALIAS_GROUP"
        result.loc[mask, "source_alias_group_epistemic_status"] = "DERIVED"

    # Every ASF row belongs to one official operator-named stop place. Pair/single
    # structure comes from the already validated directional evidence table.
    asf_members_seen: set[str] = set()
    for row in directional.itertuples(index=False):
        place_id = f"SP_ASF::{_slug(row.physical_municipality_exact)}::{_slug(row.normalized_stop_name)}"
        members = [row.source_record_a]
        if _text(row.source_record_b):
            members.append(row.source_record_b)
        for member in members:
            if member in asf_members_seen:
                raise ValueError(f"ASF record appears in multiple operator-named stop places: {member}")
            asf_members_seen.add(member)
            mask = result["master_source_record_id"].eq(member)
            if mask.sum() != 1:
                raise ValueError(f"ASF directional member not uniquely found in master: {member}")
            if result.loc[mask, "source_family"].iloc[0] != "ASF_OPERATOR_OTP":
                raise ValueError(f"Non-ASF record in ASF directional table: {member}")
            result.loc[mask, "operator_named_stop_place_id"] = place_id
            result.loc[mask, "operator_named_stop_place_status"] = "FACT_SAME_ASF_OPERATOR_NAMED_STOP_PLACE"

    master_asf = set(result.loc[result["source_family"].eq("ASF_OPERATOR_OTP"), "master_source_record_id"])
    if asf_members_seen != master_asf:
        raise ValueError(
            f"ASF stop-place coverage mismatch missing={sorted(master_asf-asf_members_seen)} extra={sorted(asf_members_seen-master_asf)}"
        )

    # Physical identity remains untouched. Even source aliases and same operator-named
    # stop places cannot populate the final physical IDs in this stage.
    if result["final_boarding_point_id"].ne("").any():
        raise ValueError("No final boarding point may be assigned in evidence-only stage")
    if result["final_stop_place_id"].ne("").any():
        raise ValueError("No final cross-operator stop place may be assigned in evidence-only stage")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "master_stop_identity_evidence_gpt_v3.csv", index=False)

    alias_groups = (
        result.groupby(["source_alias_group_id", "source_alias_group_status", "source_alias_group_epistemic_status"], dropna=False)
        .agg(source_records=("master_source_record_id", "count"), source_families=("source_family", lambda s: "|".join(sorted(set(s)))))
        .reset_index()
        .sort_values(["source_records", "source_alias_group_id"], ascending=[False, True])
    )
    alias_groups.to_csv(out / "source_alias_groups_gpt_v3.csv", index=False)

    asf_places = result[result["source_family"].eq("ASF_OPERATOR_OTP")].copy()
    place_summary = (
        asf_places.groupby(["operator_named_stop_place_id", "physical_municipality_exact"], dropna=False)
        .agg(
            source_records=("master_source_record_id", "count"),
            source_codes=("source_record_native_id", lambda s: "|".join(sorted(set(s)))),
            source_names=("source_stop_name", lambda s: "|".join(sorted(set(s)))),
        )
        .reset_index()
        .sort_values(["physical_municipality_exact", "operator_named_stop_place_id"])
    )
    place_summary.to_csv(out / "asf_operator_named_stop_places_gpt_v3.csv", index=False)

    validation = {
        "status": "PASS_IDENTITY_EVIDENCE_MATERIALIZATION",
        "source_records_count": int(len(result)),
        "distinct_source_alias_groups": int(result["source_alias_group_id"].nunique()),
        "strong_crossfeed_alias_groups": int(strong["crossfeed_key"].nunique()),
        "source_records_in_strong_alias_groups": int(len(member_to_alias)),
        "asf_source_records_count": int(len(master_asf)),
        "asf_operator_named_stop_places_count": int(place_summary["operator_named_stop_place_id"].nunique()),
        "asf_two_record_named_stop_places": int((place_summary["source_records"] == 2).sum()),
        "asf_single_record_named_stop_places": int((place_summary["source_records"] == 1).sum()),
        "final_boarding_points_assigned": 0,
        "final_cross_operator_stop_places_assigned": 0,
        "routing_terminal_selected_count": int((~result["routing_terminal_eligibility_status"].eq("NOT_EVALUATED")).sum()),
        "epistemic_note": (
            "Source alias grouping is DERIVED evidence about duplicate source representation only. "
            "ASF operator-named stop places are FACT groupings from official operator naming. "
            "Neither statement proves shared physical boarding geometry."
        ),
    }
    (out / "stop_identity_evidence_validation_gpt_v3.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    base = "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3"
    parser.add_argument("--master-municipalized", default=f"{base}/master_stop_source_records_municipalized_gpt_v3.csv")
    parser.add_argument("--asf-directional-pairs", default=f"{base}/asf_directional_pair_distances_gpt_v3.csv")
    parser.add_argument("--frozen-alias-candidates", default=f"{base}/frozen_crossfeed_alias_candidates_gpt_v3.csv")
    parser.add_argument("--output-dir", default=base)
    return parser.parse_args()


if __name__ == "__main__":
    materialize(parse_args())
