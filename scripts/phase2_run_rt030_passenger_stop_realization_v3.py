from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phase2_passenger_stop_realization_layer_v3 import (  # noqa: E402
    EXPECTED_GRAPH_EPOCH,
    RT023_FINAL_REALIZATION_CATALOG_SHA256,
    compile_rt030,
    reconcile_rt023_run_catalog_to_final,
    write_rt030,
)

EXPECTED_INPUT_SHA256 = {
    "rt023_run_realizations": "a33b24664f9cd416f16989c7a66a668a3e90a83244dd3662cac735751532adc5",
    "elementary_corridors": "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c",
    "stop_attachments": "30d64ff20e9b89c31f7878c415dd4c6bb5a0d10f51b24d041e4deb4d57e6571b",
    "corridor_stop_occurrences": "6de033c008a5b4db9a44ad31652aea8276a3b588239fbd2e2d7c23b2e88add97",
    "graph_nodes": "2ab72595b7c52d8a08ccf767a20a9a5fc00b39552b37da01a53f270467a4ca06",
    "graph_edges": "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _assert_input_hash(label: str, path: Path) -> str:
    observed = sha256_file(path)
    expected = EXPECTED_INPUT_SHA256[label]
    if observed != expected:
        raise SystemExit(f"{label} SHA256 mismatch: {observed} != {expected}")
    return observed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rt023-run-realizations", type=Path, required=True)
    ap.add_argument("--elementary-corridors", type=Path, required=True)
    ap.add_argument("--stop-attachments", type=Path, required=True)
    ap.add_argument("--corridor-stop-occurrences", type=Path, required=True)
    ap.add_argument("--graph-nodes", type=Path, required=True)
    ap.add_argument("--graph-edges", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    paths = {
        "rt023_run_realizations": args.rt023_run_realizations,
        "elementary_corridors": args.elementary_corridors,
        "stop_attachments": args.stop_attachments,
        "corridor_stop_occurrences": args.corridor_stop_occurrences,
        "graph_nodes": args.graph_nodes,
        "graph_edges": args.graph_edges,
    }
    observed_hashes = {k: _assert_input_hash(k, v) for k, v in paths.items()}

    run_catalog = pd.read_csv(args.rt023_run_realizations)
    final_catalog, reconciliation = reconcile_rt023_run_catalog_to_final(
        run_catalog,
        elementary_corridors_sha256=observed_hashes["elementary_corridors"],
        stop_attachments_sha256=observed_hashes["stop_attachments"],
        corridor_stop_occurrences_sha256=observed_hashes["corridor_stop_occurrences"],
    )
    if reconciliation["computed_final_realization_catalog_sha256"] != RT023_FINAL_REALIZATION_CATALOG_SHA256:
        raise SystemExit("RT-023 final catalog reconciliation did not prove the certified hash")

    lineage = {
        "rt023_run_realizations_sha256": observed_hashes["rt023_run_realizations"],
        "rt023_realizations_sha256": RT023_FINAL_REALIZATION_CATALOG_SHA256,
        "elementary_corridors_sha256": observed_hashes["elementary_corridors"],
        "stop_attachments_sha256": observed_hashes["stop_attachments"],
        "corridor_stop_occurrences_sha256": observed_hashes["corridor_stop_occurrences"],
        "graph_nodes_sha256": observed_hashes["graph_nodes"],
        "graph_edges_sha256": observed_hashes["graph_edges"],
    }

    result = compile_rt030(
        rt023_realizations=final_catalog,
        elementary_corridors=pd.read_csv(args.elementary_corridors),
        stop_attachments=pd.read_csv(args.stop_attachments),
        graph_nodes=pd.read_csv(args.graph_nodes),
        graph_edges=pd.read_csv(args.graph_edges),
        expected_graph_epoch=EXPECTED_GRAPH_EPOCH,
        lineage=lineage,
        rt023_lineage_reconciliation=reconciliation,
    )
    write_rt030(result, args.output_dir)
    print(json.dumps(result.audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
