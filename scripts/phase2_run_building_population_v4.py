#!/usr/bin/env python3
"""Phase 2 building-population runner with fail-closed EDIFC normalization.

Extends v3 footprint reconstruction. Active DBGT EDIFC source rows remain FACT;
for one CLASSID, EDIFC_STAT and EDIFC_TY are collapsed only by explicit non-null
consensus. Any semantic conflict fails closed instead of choosing a record by
row order, OBJECTID or construction/delivery code.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import pandas as pd

import phase2_run_building_population_v3 as v3
from src.phase2_dbgt_edifc import (
    CONSENSUS_STATUS,
    RAW_STATUS,
    consolidate_active_edifc,
)

impl = v3.impl


def enrich_dbgt(footprints, source_dir: Path):
    refs = footprints["CLASSREF"].astype(str).tolist()
    raw_edifc = impl.query_dbgt_table(
        22,
        "CLASSID",
        refs,
        "OBJECTID,CLASSID,EDIFC_STAT,EDIFC_TY,FONTE,SCALA,COD_CONS,DATA_INI,DATA_FIN",
    )
    edifc, edifc_metrics = consolidate_active_edifc(raw_edifc)
    uses = impl.query_dbgt_table(
        24,
        "CLASSREF",
        refs,
        "OBJECTID,CLASSREF,EDIFC_USO,COD_CONS,DATA_FIN",
    )

    use_map = (
        uses.groupby("CLASSREF")["EDIFC_USO"]
        .apply(lambda s: sorted(set(s.dropna().astype(str))))
        .to_dict()
        if len(uses)
        else {}
    )
    metadata = edifc.set_index("CLASSID").to_dict("index") if len(edifc) else {}

    rows = []
    for ref in refs:
        meta = metadata.get(ref, {})
        cls = impl.classify_building(
            status_code=meta.get("EDIFC_STAT"),
            type_code=meta.get("EDIFC_TY"),
            use_codes=use_map.get(ref, []),
        )
        uncertainty = list(cls.uncertainty_flags)
        source_count = int(meta.get("active_edifc_source_row_count", 0) or 0)
        if source_count > 1:
            uncertainty.append(f"multiple_active_edifc_rows_consensus={source_count}")
        rows.append({
            "CLASSREF": ref,
            "dbgt_status_fact": meta.get("EDIFC_STAT"),
            "dbgt_type_fact": meta.get("EDIFC_TY"),
            "dbgt_use_codes_fact": "|".join(use_map.get(ref, [])),
            "residential_plausibility": cls.plausibility,
            "eligible_primary": cls.eligible_primary,
            "eligible_fallback": cls.eligible_fallback,
            "residential_use_present": cls.residential_use_present,
            "mixed_use": cls.mixed_use,
            "classification_uncertainty_flags": "|".join(sorted(set(uncertainty))),
            "classification_epistemic_status": "DERIVED_FROM_DBGT_STATUS_USAGE_TYPE_WITH_EDIFC_CONSENSUS",
        })
    classification = pd.DataFrame(rows)
    gdf = footprints.merge(classification, on="CLASSREF", how="left", validate="one_to_one")

    volume_refs = gdf.loc[
        gdf["eligible_primary"] | gdf["eligible_fallback"], "CLASSREF"
    ].astype(str).tolist()
    volumes = impl.query_dbgt_table(
        0,
        "CEDIUV",
        volume_refs,
        "OBJECTID,CLASSID,CEDIUV,UN_VOL_AV,UN_VOL_EX,UN_VOL_QE,Shape_Area,COD_CONS,DATA_FIN",
    ) if volume_refs else pd.DataFrame()

    volume_summary = {}
    if len(volumes):
        for ref, group in volumes.groupby("CEDIUV"):
            heights = pd.to_numeric(group["UN_VOL_AV"], errors="coerce")
            areas = pd.to_numeric(group["Shape_Area"], errors="coerce")
            complete = (
                len(group) > 0
                and heights.notna().all()
                and areas.notna().all()
                and (heights > 0).all()
                and (areas > 0).all()
            )
            proxy = float((heights * areas).sum()) if complete else math.nan
            volume_summary[str(ref)] = (complete, proxy, len(group))
    gdf["dbgt_volume_units_count"] = gdf["CLASSREF"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[2]
    )
    gdf["dbgt_volume_complete"] = gdf["CLASSREF"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[0]
    )
    gdf["dbgt_volume_proxy_m3"] = gdf["CLASSREF"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[1]
    )
    gdf["allocation_weight_basis"] = gdf["dbgt_volume_complete"].map(
        lambda complete: "DBGT_VOLUME_PROXY_COMPLETE" if complete else "DBGT_FOOTPRINT_AREA"
    )

    raw_edifc_path = source_dir / "dbgt_edifc_active_source_rows.csv.gz"
    consensus_path = source_dir / "dbgt_edifc_consensus_selected.csv.gz"
    uses_path = source_dir / "dbgt_uses_selected.csv.gz"
    vol_path = source_dir / "dbgt_volume_units_selected.csv.gz"
    raw_edifc.sort_values(["CLASSID", "OBJECTID"]).to_csv(
        raw_edifc_path, index=False, compression="gzip"
    )
    edifc.sort_values("CLASSID").to_csv(consensus_path, index=False, compression="gzip")
    uses.sort_values(["CLASSREF", "EDIFC_USO"]).to_csv(
        uses_path, index=False, compression="gzip"
    )
    if len(volumes):
        volumes.sort_values(["CEDIUV", "CLASSID"]).to_csv(
            vol_path, index=False, compression="gzip"
        )
    else:
        pd.DataFrame().to_csv(vol_path, index=False, compression="gzip")

    info = {
        "edifc_url": f"{impl.DBGT_BASE}/22",
        "uses_url": f"{impl.DBGT_BASE}/24",
        "volume_url": f"{impl.DBGT_BASE}/0",
        "epistemic_status": "FACT_DBGT_SOURCE_ROWS_PLUS_DERIVED_EDIFC_CONSENSUS",
        **edifc_metrics,
        "consensus_edifc_rows": len(edifc),
        "active_use_rows": len(uses),
        "active_volume_unit_rows": len(volumes),
        "volume_complete_buildings": int(gdf["dbgt_volume_complete"].sum()),
        "raw_edifc_snapshot_sha256": impl.sha256_file(raw_edifc_path),
        "consensus_edifc_snapshot_sha256": impl.sha256_file(consensus_path),
        "uses_snapshot_sha256": impl.sha256_file(uses_path),
        "volume_snapshot_sha256": impl.sha256_file(vol_path),
    }
    return gdf, info


def _postprocess_edifc_outputs(output_dir: Path) -> None:
    manifest_path = output_dir / "building_population_source_manifest.json"
    validation_path = output_dir / "building_population_validation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    source = manifest["sources"]["lombardia_dbgt_attributes"]

    source["raw_edifc_epistemic_status"] = RAW_STATUS
    source["consensus_edifc_epistemic_status"] = CONSENSUS_STATUS
    manifest["source_hierarchy"] = [
        x.replace(
            "FACT Regione Lombardia DBGT active footprint parts/status/use/available volumetric units; DERIVED building geometry union by CLASSREF",
            "FACT Regione Lombardia DBGT active footprint parts and EDIFC source rows/use/available volumetric units; DERIVED building geometry union by CLASSREF and fail-closed EDIFC semantic consensus",
        )
        for x in manifest["source_hierarchy"]
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    validation.update({
        "dbgt_raw_edifc_epistemic_status": RAW_STATUS,
        "dbgt_consensus_edifc_epistemic_status": CONSENSUS_STATUS,
        "dbgt_raw_active_edifc_rows": source["raw_active_edifc_rows"],
        "dbgt_unique_active_edifc_classid": source["unique_active_edifc_classid"],
        "dbgt_classid_with_multiple_active_edifc_rows": source["classid_with_multiple_active_edifc_rows"],
        "dbgt_extra_active_edifc_rows_collapsed": source["extra_active_edifc_rows_collapsed"],
        "dbgt_max_active_edifc_rows_per_classid": source["max_active_edifc_rows_per_classid"],
        "dbgt_edifc_semantic_conflict_classid": source["semantic_conflict_classid"],
    })
    validation["limitations"].append(
        "DBGT can expose multiple active EDIFC attribute rows for one CLASSID. Phase 2 preserves those FACT rows and derives a single classification input only when all non-null EDIFC_STAT and EDIFC_TY values agree; semantic conflicts fail closed."
    )
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    impl.write_checksums(output_dir)


impl.enrich_dbgt = enrich_dbgt


if __name__ == "__main__":
    result = impl.main()
    output_dir = Path("outputs/phase2")
    if "--output-dir" in sys.argv:
        output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    v3._postprocess_epistemic_outputs(output_dir)
    _postprocess_edifc_outputs(output_dir)
    print(json.dumps(json.loads((output_dir / "building_population_validation.json").read_text()), ensure_ascii=False, indent=2))
    sys.exit(result)
