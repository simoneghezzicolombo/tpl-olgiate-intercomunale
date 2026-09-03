#!/usr/bin/env python3
"""Replay Gate B's own GTFS-stop baseline through the Gate F coverage bridge."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_b_bridge import evaluate_candidate_coverage  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-dir", type=Path, required=True)
    p.add_argument("--gate-b-commit", required=True)
    p.add_argument("--threshold-min", type=float, required=True)
    p.add_argument("--max-stop-snap-m", type=float, required=True)
    p.add_argument("--walk-connector-kmh", type=float, required=True)
    args = p.parse_args()
    try:
        artifact = args.artifact_dir
        stops = pd.read_csv(artifact / "gtfs_core_stops.csv", dtype={"stop_id": str, "PRO_COM_T": str})
        snap_ok = stops["snap_ok"].astype(str).str.lower().isin({"true", "1"})
        usable = stops.loc[snap_ok].copy()
        candidate = pd.DataFrame({
            "scenario_id": "GATE_B_BASELINE_REPLAY",
            "stop_id": usable["stop_id"].astype(str),
            "stop_lat": usable["stop_lat"],
            "stop_lon": usable["stop_lon"],
            "territory_id": usable["PRO_COM_T"].astype(str),
            "epistemic_status": "FACT",
            "source": "GATE_B_PASS_GTFS_CORE_STOPS",
        })
        coverage = pd.read_csv(artifact / "coverage_summary.csv")
        target_rows = coverage.loc[
            coverage["scope"].eq("core_total")
            & pd.to_numeric(coverage["threshold_min"], errors="coerce").eq(args.threshold_min)
        ]
        if len(target_rows) != 1:
            raise ValueError("Gate B coverage summary does not contain exactly one requested core_total threshold")
        target = float(target_rows.iloc[0]["coverage_pct"])
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            stops_path = tmpdir / "candidate_stops.csv"
            policy_path = tmpdir / "policy.json"
            candidate.to_csv(stops_path, index=False)
            policy_path.write_text(json.dumps({
                "schema_version": 1,
                "comparison_id": "GATE_B_PASS_BASELINE_REPLAY",
                "threshold_min": args.threshold_min,
                "max_stop_snap_m": args.max_stop_snap_m,
                "walk_connector_kmh": args.walk_connector_kmh,
                "territory_definition_id": "ISTAT_CORE_MUNICIPALITIES",
            }), encoding="utf-8")
            result = evaluate_candidate_coverage(
                stops_path,
                artifact / "walk_graph_nodes.csv",
                artifact / "walk_graph_edges.csv",
                artifact / "population_accessibility.csv",
                policy_path,
                gate_b_commit=args.gate_b_commit,
            )
        actual = float(result.iloc[0]["population_covered_pct"])
        error = abs(actual - target)
        print(f"Gate B baseline replay target={target:.12f} actual={actual:.12f} abs_error={error:.12g}")
        if error > 1e-9:
            raise ValueError("Gate F Gate B bridge does not reproduce validated Gate B baseline coverage")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_GATE_B_REGRESSION_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
