"""Pinned real RT-030 occurrence audit. No new route or service selection."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences, decimal, concatenate_available
from src.phase2_rt031_typed_composition_v3 import payload_hash

EPOCH = "RT017::2026-09-05T13:45:50Z::466f562f95805cb1"
INPUTS = {
    "patterns": ("rt030/rt030_realization_passenger_stop_patterns.csv", "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e"),
    "occurrences": ("rt030/rt030_realization_stop_occurrences.csv", "124494b69713a7fe1792d241415d3437d2e87414752eb74603e5ec6aaf8bda37"),
    "corridors": ("rt022/elementary_corridors_for_reciprocity.csv", "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c"),
    "stops": ("rt022/stop_attachments.csv", "30d64ff20e9b89c31f7878c415dd4c6bb5a0d10f51b24d041e4deb4d57e6571b"),
    "edges": ("rt017/frozen_graph_edges.csv.gz", "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19"),
}


def run(root, out):
    tables, hashes = {}, {}
    for label, (name, expected) in INPUTS.items():
        path = root / name
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != expected:
            raise ValueError(f"frozen {label} SHA256 mismatch")
        hashes[label] = observed
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8", newline="") as f:
            tables[label] = list(csv.DictReader(f))
    classes = Counter(s["service_class"] for s in tables["stops"])
    assert len(tables["stops"]) == 36 and classes == {"CONVENTIONAL_TPL": 35, "SPECIAL_SERVICE": 1}
    special = [s for s in tables["stops"] if s["service_class"] == "SPECIAL_SERVICE"]
    assert special[0]["stop_place_id"] == "SPECIAL::CASA_DI_COMUNITA_OLGIATE"
    assert special[0]["automatic_materialization_eligible"].lower() == "false"
    assert len(tables["patterns"]) == 288 and len(tables["occurrences"]) == 597
    audit030 = json.loads((root / "rt030/rt030_audit.json").read_text())
    assert audit030["status"] == "PASS"
    reconciliation = audit030["rt023_lineage_reconciliation"]
    assert reconciliation["hash_reconciliation_proven"] is True
    assert reconciliation["computed_final_realization_catalog_sha256"] == "24d806b3b30cf75c91cf531746bada443bf3d5bedf3878e9587778cad7c9d36a"
    bound = bind_occurrences(**tables, epoch=EPOCH)
    manifests = []
    for rid, item in bound.items():
        # Identity preservation for a single atomic realization. No multi-link
        # route domain is invented to manufacture a production composition PASS.
        replay = concatenate_available(bound, [rid])
        assert len(replay["payload"]["visits"]) == len(item["payload"]["visits"])
        manifests.append({"realization_id": rid, "binding_sha256": item["sha256"],
                          "occurrences": len(item["payload"]["visits"]),
                          "carrier_edges": len(item["payload"]["carrier"]),
                          "atomic_expansion_sha256": replay["sha256"]})
    positions = [decimal(r["path_position"]) for r in tables["occurrences"]]
    audit = {"status": "PASS_PINNED_RT030_OCCURRENCE_BINDING_ONLY", "epistemic_status": "DERIVED",
             "input_kind": "PINNED_REAL_TERRITORIAL_EVIDENCE", "graph_epoch": EPOCH,
             "input_sha256": hashes, "realizations": len(bound), "occurrences": len(positions),
             "fractional_occurrences": sum(p != int(p) for p in positions),
             "evidence_types": dict(sorted(Counter(r["evidence_type"] for r in tables["occurrences"]).items())),
             "all_occurrences_preserved": sum(m["occurrences"] for m in manifests) == 597,
             "manifest_sha256": payload_hash(manifests), "rt023_final_catalog_sha256": reconciliation["computed_final_realization_catalog_sha256"],
             "special_service_promoted": False, "pickup_dropoff_assigned": False,
             "turn_composition_status": "UNKNOWN_EVIDENCE", "network_selected": False,
             "full_rt031_production_gate_pass": False}
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (("binding_manifest.json", manifests), ("real_binding_audit.json", audit)):
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs, args.out)
