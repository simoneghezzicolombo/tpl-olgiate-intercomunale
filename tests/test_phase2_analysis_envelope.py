from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/phase2/analysis_envelope"
SRC = ROOT / "data/phase2/analysis_envelope/source"
BASELINE = "147ad941579eb7ef17a5a54c19a5f820e5a226d4"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_validation_contract_pass_and_source_closed():
    val = json.loads((OUT / "analysis_envelope_validation.json").read_text(encoding="utf-8"))
    assert val["status"] == "PASS_ANALYSIS_ENVELOPE"
    assert val["baseline_commit"] == BASELINE
    comp=pd.read_csv(OUT / "envelope_rule_comparison.csv")
    priority=["ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY","ADJACENCY_1_PLUS_V1_WALK_GUARD","METRIC_GUARD_ONLY"]
    supported=set(comp.loc[comp.within_frozen_graph_bbox_plus_probe.astype(bool) & comp.contains_core_v1_guard.astype(bool),"rule"])
    expected=next(name for name in priority if name in supported)
    assert val["selected_rule"] == expected
    assert abs(float(val["edge_guard_m"]) - 1210.0) < 1e-9
    assert val["acquisition_used_this_run"] is False
    assert val["edge_effect_audit"]["core_guard_contained"] is True
    assert isinstance(val["edge_effect_audit"]["first_order_shell_guard_contained"], bool)
    assert val["edge_effect_audit"]["selected_plus_probe_within_frozen_gate_d_bbox"] is True


def test_core_context_equity_separation():
    inv = pd.read_csv(OUT / "municipalities_intersected.csv", dtype={"procom": str})
    core = inv[inv.analysis_role == "CORE"]
    context = inv[inv.analysis_role == "CONTEXT"]
    assert len(core) == 5
    assert set(core.procom.str.zfill(6)) == {"097010", "097012", "097058", "097074", "097092"}
    assert set(core.equity_scope) == {"DECISION_CORE_EQUITY_OBLIGATION"}
    assert not context.empty
    assert set(context.equity_scope) == {"CONTEXT_ONLY_NO_EQUAL_EQUITY_OBLIGATION"}


def test_multiple_rules_compared_without_topology_choice():
    comp = pd.read_csv(OUT / "envelope_rule_comparison.csv")
    assert set(comp.rule) == {
        "METRIC_GUARD_ONLY",
        "ADJACENCY_1_PLUS_V1_WALK_GUARD",
        "ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY",
    }
    assert int(comp.selected.sum()) == 1
    val = json.loads((OUT / "analysis_envelope_validation.json").read_text(encoding="utf-8"))
    for key in ["topology_selected", "final_stop_selected", "headway_selected", "manual_external_municipality_whitelist_used", "np_random_used", "synthetic_data_used", "v1_outputs_modified"]:
        assert val["prohibitions"][key] is False


def test_primary_source_snapshot_checksums():
    manifest = json.loads((SRC / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["baseline_commit"] == BASELINE
    assert manifest["source_state"] == "FROZEN_AFTER_PRIMARY_ACQUISITION"
    assert manifest["buildings"]["license"] == "CC-BY-4.0"
    assert manifest["graph_epoch"]["epoch_id"] == "gate-d-2026-09-03-834d5caa0bfd"
    for filename, expected in manifest["frozen_source_files_sha256"].items():
        assert (SRC / filename).exists()
        assert sha256(SRC / filename) == expected


def test_all_requested_entity_classes_are_materialised():
    val = json.loads((OUT / "analysis_envelope_validation.json").read_text(encoding="utf-8"))
    c = val["counts"]
    assert c["municipalities"] > 5
    assert c["census_sections"] > 0
    assert c["buildings"] > 0
    assert c["frozen_road_edges"] > 0
    assert c["official_bus_stop_records"] > 0
    assert c["rail_anchor_records"] >= 1
    assert len(pd.read_csv(OUT / "census_sections_intersected.csv.gz")) == c["census_sections"]
    assert len(pd.read_csv(OUT / "buildings_intersected.csv.gz")) == c["buildings"]
    assert len(pd.read_csv(OUT / "roads_intersected.csv.gz")) == c["frozen_road_edges"]
    assert len(pd.read_csv(OUT / "stops_and_anchors_intersected.csv")) == c["anchor_records"]


def test_output_checksum_manifest_reconciles():
    for line in (OUT / "analysis_envelope_checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, filename = line.split("  ", 1)
        assert sha256(OUT / filename) == expected


def test_no_example_external_whitelist_or_randomness_in_production_code():
    code = (ROOT / "scripts/phase2_analysis_envelope.py").read_text(encoding="utf-8")
    assert "np.random" not in code
    assert "random." not in code
    for forbidden in ["Merate", "Imbersago", "Airuno"]:
        assert forbidden not in code
