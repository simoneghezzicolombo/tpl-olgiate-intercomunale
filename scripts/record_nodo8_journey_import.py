"""Record the byte-preserved historical assets imported from the published Git tree."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "dietro-l-analisi"
preserved = [
    path for path in JOURNEY.rglob("*")
    if path.is_file() and (
        path.suffix == ".b64" or ".b64." in path.name or
        "vendor" in path.relative_to(JOURNEY).parts or
        path.name in ("journey-data.js", "legacy-geo-data.js", "data-manifest.json",
                      "current-routes-kml-exact-provenance.json", "exact-route-lineage.json")
    )
]
manifest = {
    "contract": "nodo8_journey_upstream_import_v1",
    "upstream_ref_at_import": "origin/gh-pages",
    "upstream_commit": "104e8f2f0a801cffb15698aa06a8c2bd98c0dc6e",
    "imported_on": "2026-10-07",
    "integrated_on": "2026-10-08",
    "scope": "Historical process assets, not current Nodo8 population or route proof.",
    "legacy_geo_data_original_path": "geo-data.js",
    "nodo8_current_source": "../assets/nodo8-proposal.json",
    "preserved_assets": [
        {"path": path.relative_to(JOURNEY).as_posix(),
         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(preserved)
    ],
}
if __name__ == "__main__":
    # Verify the original archive, not merely the current checkout.
    with ZipFile(ROOT / "cache/nodo8-journey-upstream.zip") as upstream:
        for path in preserved:
            original = "geo-data.js" if path.name == "legacy-geo-data.js" else "dietro-l-analisi/" + path.relative_to(JOURNEY).as_posix()
            if upstream.read(original) != path.read_bytes():
                raise SystemExit(f"Upstream bytes differ: {path.name}")
    (JOURNEY / "upstream-import.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(preserved)} historical/vendor assets.")
