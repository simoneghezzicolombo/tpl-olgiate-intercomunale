#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_frozen_graph import bootstrap_sources, materialize_all, verify_source_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="data/phase2/frozen_gate_d/source")
    parser.add_argument("--output-dir", default="outputs/phase2/frozen_gate_d")
    parser.add_argument("--bootstrap-artifact-dir")
    parser.add_argument(
        "--arriva-zip",
        default="data/raw/gtfs/agency_arriva/GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip",
    )
    parser.add_argument(
        "--lineelecco-zip",
        default="data/raw/gtfs/agency_lineelecco/GTFS_invernale_2025-2026_Linee_Lecco.zip",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    if args.bootstrap_artifact_dir:
        bootstrap_sources(Path(args.bootstrap_artifact_dir), source_dir)
    verify_source_dir(source_dir)
    validation = materialize_all(
        source_dir,
        Path(args.output_dir),
        Path(args.arriva_zip),
        Path(args.lineelecco_zip),
    )
    graph = validation["graph"]
    anchors = validation["anchors"]
    reduced = validation["reduced_transfer_graph"]
    print(
        "Frozen Gate D graph:",
        validation["epoch_id"],
        "nodes=", graph["graph_nodes"],
        "edges=", graph["graph_directed_edges"],
        "anchors=", anchors["anchors_total"],
        "seed_paths=", reduced["ordered_seed_path_records"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
