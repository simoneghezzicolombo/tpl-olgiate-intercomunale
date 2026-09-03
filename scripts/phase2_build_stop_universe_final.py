#!/usr/bin/env python3
"""Final audited runner for the Phase-2 candidate-stop universe.

It preserves the existing materialisation pipeline but fixes audit findings:
1. catchment-Jaccard pruning keeps cellsets aligned after deterministic coordinate sort;
2. each physical existing-stop cluster uses all snapped official GTFS records as
   walking-network sources, rather than one representative record;
3. known UTF-8-as-Latin-1 mojibake is removed from generated text labels only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_stop_cluster import walk_distances_to_stop_records  # noqa: E402
from src.phase2_stop_core import THRESHOLDS, cell_membership, load_walk_graph, sha256  # noqa: E402
from src.phase2_stop_metrics_v2 import geometric_overlap_prune  # noqa: E402

TEXT_REPLACEMENTS = {
    "Ã€": "À", "Ãˆ": "È", "Ã‰": "É", "ÃŒ": "Ì", "Ã’": "Ò", "Ã™": "Ù",
    "Ã ": "à", "Ã¨": "è", "Ã©": "é", "Ã¬": "ì", "Ã²": "ò", "Ã¹": "ù",
    "Ã§": "ç", "Ãª": "ê", "Ã´": "ô", "Â°": "°", "Âª": "ª",
}
SUSPICIOUS_TEXT_MARKERS = ("Ã", "Â")


def _load_base_runner():
    path = ROOT / "scripts" / "phase2_build_stop_universe.py"
    spec = importlib.util.spec_from_file_location("phase2_stop_universe_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import base stop-universe runner from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.geometric_overlap_prune = geometric_overlap_prune
    return module


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def _rebuild_existing_cluster_catchments(gate_b_dir: Path, output_dir: Path) -> None:
    directed, _, _, _, _ = load_walk_graph(gate_b_dir)
    cells = pd.read_csv(gate_b_dir / "population_accessibility.csv", dtype={"PRO_COM_T": str})
    stops = pd.read_csv(output_dir / "existing_official_stops.csv", dtype={"stop_id": str})
    summary_rows = []
    cell_rows = []
    for cluster_id, group in stops.groupby("physical_cluster_id", sort=True):
        snapped = group[_bool_series(group["snap_ok"])]
        if snapped.empty:
            continue
        distances = walk_distances_to_stop_records(directed, snapped, cutoff=max(THRESHOLDS))
        for threshold in THRESHOLDS:
            mask, _ = cell_membership(cells, distances, threshold)
            summary_rows.append(
                {
                    "physical_cluster_id": cluster_id,
                    "threshold_min": threshold,
                    "population_reachable_2025": float(cells.loc[mask, "pop_calibrated_2025"].sum()),
                    "population_denominator_2025": float(cells["pop_calibrated_2025"].sum()),
                    "cell_count": int(mask.sum()),
                    "gtfs_records_used_as_sources": int(len(snapped)),
                    "epistemic_status": "MODEL_OUTPUT_GATE_B_WALK_GRAPH_MULTI_SOURCE_PHYSICAL_CLUSTER",
                }
            )
        mask, total = cell_membership(cells, distances, 12)
        for index in cells.index[mask]:
            cell_rows.append(
                {
                    "physical_cluster_id": cluster_id,
                    "cell_id": cells.at[index, "cell_id"],
                    "walk_min_to_stop": float(total.at[index]),
                    "pop_calibrated_2025": float(cells.at[index, "pop_calibrated_2025"]),
                }
            )
    pd.DataFrame(summary_rows).to_csv(output_dir / "existing_stop_catchment_summary.csv", index=False)
    pd.DataFrame(cell_rows).to_csv(output_dir / "existing_stop_catchment_cells_12min.csv", index=False)


def _normalize_generated_text_labels(output_dir: Path) -> None:
    """Normalize labels only; fail if suspicious mojibake remains in text outputs."""
    for path in sorted(output_dir.iterdir()):
        if path.suffix.lower() not in {".csv", ".geojson", ".json"}:
            continue
        if not path.name.startswith(
            ("existing_", "accessibility_", "settlement_", "proposed_", "interchange_", "candidate_", "stop_universe_")
        ):
            continue
        text = path.read_text(encoding="utf-8")
        for broken, fixed in TEXT_REPLACEMENTS.items():
            text = text.replace(broken, fixed)
        if any(marker in text for marker in SUSPICIOUS_TEXT_MARKERS):
            sample = next(line for line in text.splitlines() if any(marker in line for marker in SUSPICIOUS_TEXT_MARKERS))
            raise RuntimeError(f"Unresolved generated-text mojibake in {path}: {sample[:240]}")
        path.write_text(text, encoding="utf-8", newline="")


def _rewrite_validation_and_checksums(output_dir: Path) -> None:
    validation_path = output_dir / "stop_universe_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["existing_physical_cluster_catchment_method"] = (
        "MULTI_SOURCE_ALL_SNAPPED_GTFS_RECORDS_PER_40M_CLUSTER"
    )
    validation["pruning_cellset_alignment"] = "STABLE_PRE_SORT_KEYS"
    validation["text_label_normalization"] = "KNOWN_UTF8_AS_LATIN1_MOJIBAKE_ONLY"
    validation["final_network_selected"] = False
    validation["headway_modified"] = False
    validation["timetable_modified"] = False
    validation["budget_modified"] = False
    validation["ranking_produced"] = False
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    targets = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and path.name != "stop_universe_checksums.sha256"
        and path.name.startswith(
            (
                "existing_",
                "accessibility_",
                "settlement_",
                "proposed_",
                "interchange_",
                "candidate_",
                "stop_universe_",
            )
        )
    )
    lines = [f"{sha256(path)}  {path.name}" for path in targets]
    (output_dir / "stop_universe_checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gate-b-dir", required=True)
    parser.add_argument("--output-dir", default="outputs/phase2")
    known, _ = parser.parse_known_args()

    base = _load_base_runner()
    result = base.main()
    output_dir = Path(known.output_dir)
    _rebuild_existing_cluster_catchments(Path(known.gate_b_dir), output_dir)
    _normalize_generated_text_labels(output_dir)
    _rewrite_validation_and_checksums(output_dir)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
