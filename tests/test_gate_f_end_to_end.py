import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric(value, status, source, unit, semantics, basis):
    return value, status, source, unit, semantics, basis


def _write_pipeline_fixture(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    catalog = pd.DataFrame([
        {"scenario_id": "BASE", "scenario_name": "Baseline test fixture", "topology_family": "CURRENT", "is_baseline": True, "scenario_epistemic_status": "RECONSTRUCTED", "scenario_source": "E2E_TEST"},
        {"scenario_id": "ALT", "scenario_name": "Alternative test fixture", "topology_family": "OTHER", "is_baseline": False, "scenario_epistemic_status": "MODEL OUTPUT", "scenario_source": "E2E_TEST"},
    ])
    gate_d = pd.DataFrame([
        {"scenario_id": sid, "road_feasible": True, "road_feasible__status": "DERIVED", "road_feasible__source": "E2E_D", "road_feasible__unit": "boolean", "road_feasible__semantics": "HARD_ELIGIBILITY_CONSTRAINT", "road_feasible__comparison_basis": "E2E_ROAD_RULESET"}
        for sid in ("BASE", "ALT")
    ])
    gate_b = pd.DataFrame([
        {"scenario_id": "BASE", "population_covered_pct": 50.0, "population_covered_pct__status": "MODEL OUTPUT", "population_covered_pct__source": "E2E_B", "population_covered_pct__unit": "%", "population_covered_pct__semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR", "population_covered_pct__comparison_basis": "E2E_POP_BASIS", "territories_served_count": 3, "territories_served_count__status": "MODEL OUTPUT", "territories_served_count__source": "E2E_B", "territories_served_count__unit": "count", "territories_served_count__semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS", "territories_served_count__comparison_basis": "E2E_TERRITORY_BASIS"},
        {"scenario_id": "ALT", "population_covered_pct": 80.0, "population_covered_pct__status": "MODEL OUTPUT", "population_covered_pct__source": "E2E_B", "population_covered_pct__unit": "%", "population_covered_pct__semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR", "population_covered_pct__comparison_basis": "E2E_POP_BASIS", "territories_served_count": 5, "territories_served_count__status": "MODEL OUTPUT", "territories_served_count__source": "E2E_B", "territories_served_count__unit": "count", "territories_served_count__semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS", "territories_served_count__comparison_basis": "E2E_TERRITORY_BASIS"},
    ])
    gate_c = pd.DataFrame([
        {"scenario_id": "BASE", "s8_useful_connection_pct": 60.0, "s8_useful_connection_pct__status": "MODEL OUTPUT", "s8_useful_connection_pct__source": "E2E_C", "s8_useful_connection_pct__unit": "%", "s8_useful_connection_pct__semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR", "s8_useful_connection_pct__comparison_basis": "E2E_S8_BASIS"},
        {"scenario_id": "ALT", "s8_useful_connection_pct": 90.0, "s8_useful_connection_pct__status": "MODEL OUTPUT", "s8_useful_connection_pct__source": "E2E_C", "s8_useful_connection_pct__unit": "%", "s8_useful_connection_pct__semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR", "s8_useful_connection_pct__comparison_basis": "E2E_S8_BASIS"},
    ])
    gate_e = pd.DataFrame([
        {"scenario_id": "BASE", "headway_combined_min": 60.0, "headway_combined_min__status": "MODEL OUTPUT", "headway_combined_min__source": "E2E_E", "headway_combined_min__unit": "min", "headway_combined_min__semantics": "RATE_EQUIVALENT_NOT_MAX_GAP", "headway_combined_min__comparison_basis": "E2E_SERVICE_WINDOW", "annual_bus_km": 100000.0, "annual_bus_km__status": "MODEL OUTPUT", "annual_bus_km__source": "E2E_E", "annual_bus_km__unit": "bus-km/year", "annual_bus_km__semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE", "annual_bus_km__comparison_basis": "E2E_ANNUAL_BASIS", "peak_buses_required": 2, "peak_buses_required__status": "MODEL OUTPUT", "peak_buses_required__source": "E2E_E", "peak_buses_required__unit": "vehicles", "peak_buses_required__semantics": "SIMULTANEOUS_PEAK_VEHICLES", "peak_buses_required__comparison_basis": "E2E_PEAK_BASIS"},
        {"scenario_id": "ALT", "headway_combined_min": 30.0, "headway_combined_min__status": "MODEL OUTPUT", "headway_combined_min__source": "E2E_E", "headway_combined_min__unit": "min", "headway_combined_min__semantics": "RATE_EQUIVALENT_NOT_MAX_GAP", "headway_combined_min__comparison_basis": "E2E_SERVICE_WINDOW", "annual_bus_km": 90000.0, "annual_bus_km__status": "MODEL OUTPUT", "annual_bus_km__source": "E2E_E", "annual_bus_km__unit": "bus-km/year", "annual_bus_km__semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE", "annual_bus_km__comparison_basis": "E2E_ANNUAL_BASIS", "peak_buses_required": 1, "peak_buses_required__status": "MODEL OUTPUT", "peak_buses_required__source": "E2E_E", "peak_buses_required__unit": "vehicles", "peak_buses_required__semantics": "SIMULTANEOUS_PEAK_VEHICLES", "peak_buses_required__comparison_basis": "E2E_PEAK_BASIS"},
    ])
    paths = {}
    for name, frame in {"catalog": catalog, "gate_b": gate_b, "gate_c": gate_c, "gate_d": gate_d, "gate_e": gate_e}.items():
        path = root / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _build(root: Path, paths):
    metrics = root / "gate_f_scenario_metrics.csv"
    exclusions = root / "excluded_scenarios.csv"
    assembly = root / "assembly_manifest.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts/gate_f_build_inputs.py"),
        "--catalog", _relative(paths["catalog"]),
        "--gate-b", _relative(paths["gate_b"]),
        "--gate-c", _relative(paths["gate_c"]),
        "--gate-d", _relative(paths["gate_d"]),
        "--gate-e", _relative(paths["gate_e"]),
        "--output", _relative(metrics),
        "--exclusions-output", _relative(exclusions),
        "--manifest-output", _relative(assembly),
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return metrics, exclusions, assembly


def _status_bundle(root: Path) -> Path:
    gates = {}
    for index, gate in enumerate("ABCDE", start=10):
        evidence = root / f"gate_{gate.lower()}_evidence.md"
        evidence.write_text(f"Gate {gate} E2E fixture evidence\n", encoding="utf-8")
        gates[gate] = {
            "verdict": "PASS",
            "commit_sha": format(index, "x") * 40,
            "source_branch": f"gate-{gate.lower()}-workstream",
            "evidence_files": [{"path": _relative(evidence), "sha256": _sha(evidence)}],
        }
    bundle = {"schema_version": 1, "integration_id": "E2E_TEST_ONLY", "gates": gates}
    path = root / "status_bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def _run_pareto(root: Path, metrics: Path, assembly: Path, extra_args):
    out = root / "out"
    cmd = [
        sys.executable,
        str(ROOT / "scripts/13_gate_f_pareto.py"),
        "--input", _relative(metrics),
        "--assembly-manifest", _relative(assembly),
        "--output-dir", _relative(out),
        *extra_args,
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return result, out


def test_full_verified_pipeline_can_reach_unique_robust_pass():
    with tempfile.TemporaryDirectory(prefix=".gate_f_e2e_", dir=ROOT) as temp:
        root = Path(temp)
        paths = _write_pipeline_fixture(root)
        metrics, _, assembly = _build(root, paths)
        status = _status_bundle(root)
        result, out = _run_pareto(root, metrics, assembly, ["--gate-status-file", _relative(status)])
        assert result.returncode == 0, result.stdout + result.stderr
        verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
        assert verdict["verdict"] == "PASS"
        assert verdict["recommended_scenario_id"] == "ALT"
        assert verdict["recommendation_status"] == "UNIQUE_ROBUST_PARETO_DOMINANT"
        assert (out / "verified_assembly_manifest.json").exists()
        assert (out / "verified_gate_status_bundle.json").exists()


def test_manual_all_pass_cannot_bypass_status_evidence():
    with tempfile.TemporaryDirectory(prefix=".gate_f_e2e_", dir=ROOT) as temp:
        root = Path(temp)
        paths = _write_pipeline_fixture(root)
        metrics, _, assembly = _build(root, paths)
        manual = []
        for gate in "ABCDE":
            manual.extend(["--gate-status", f"{gate}=PASS"])
        result, out = _run_pareto(root, metrics, assembly, manual)
        assert result.returncode == 2
        verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
        assert verdict["verdict"] == "PROVISIONAL"
        assert verdict["recommendation_status"] == "BLOCKED_UNVERIFIED_GATE_STATUS_EVIDENCE"
        assert verdict["recommended_scenario_id"] is None


def test_tampering_after_assembly_is_refused_before_pareto():
    with tempfile.TemporaryDirectory(prefix=".gate_f_e2e_", dir=ROOT) as temp:
        root = Path(temp)
        paths = _write_pipeline_fixture(root)
        metrics, _, assembly = _build(root, paths)
        metrics.write_text(metrics.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        status = _status_bundle(root)
        result, _ = _run_pareto(root, metrics, assembly, ["--gate-status-file", _relative(status)])
        assert result.returncode != 0
        assert "REFUSED_ASSEMBLY_MANIFEST" in result.stderr
