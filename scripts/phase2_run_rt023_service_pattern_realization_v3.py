from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2_service_pattern_realization_bridge_v3 import compile_rt023_bridge, write_bridge_result


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compile RT-022 structural links into RT-023 topology-neutral directed service-pattern fragments."
    )
    p.add_argument("--reciprocal-links", type=Path, required=True)
    p.add_argument("--structures", type=Path, required=True)
    p.add_argument("--elementary-corridors", type=Path, required=True)
    p.add_argument("--corridor-stop-occurrences", type=Path, required=True)
    p.add_argument("--rt022-audit", type=Path)
    p.add_argument("--output-dir", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    inputs = {
        "reciprocal_structural_links": args.reciprocal_links,
        "minimum_topology_neutral_backbone_universe": args.structures,
        "elementary_corridors_for_reciprocity": args.elementary_corridors,
        "corridor_stop_occurrences": args.corridor_stop_occurrences,
    }
    lineage = {f"{key}_sha256": _sha256(path) for key, path in inputs.items()}

    expected_graph_epoch = None
    if args.rt022_audit:
        lineage["rt022_minimum_backbone_audit_sha256"] = _sha256(args.rt022_audit)
        audit = json.loads(args.rt022_audit.read_text(encoding="utf-8"))
        expected_graph_epoch = (
            audit.get("graph_epoch_id")
            or audit.get("graph_epoch")
            or audit.get("rt017_graph_epoch_id")
        )

    result = compile_rt023_bridge(
        reciprocal_links=pd.read_csv(args.reciprocal_links),
        structures=pd.read_csv(args.structures),
        elementary_corridors=pd.read_csv(args.elementary_corridors),
        corridor_stop_occurrences=pd.read_csv(args.corridor_stop_occurrences),
        expected_graph_epoch_id=expected_graph_epoch,
        lineage=lineage,
    )
    write_bridge_result(result, args.output_dir)
    print(json.dumps(result.audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
