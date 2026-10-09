"""Materialise an explicit reviewed file list; no deployment or repository deletion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "dietro-l-analisi/"
runtime = [
    "index.html", "favicon.svg", "journey.css", "journey-nodo8.css",
    "journey-bootstrap.mjs", "journey-effects.js", "journey-runtime-policy.js",
    "journey-experience-policy.js", "journey-explore-prelude.js", "journey.js",
    "journey-director.js", "journey-lens.js", "journey-lineage.js",
    "journey-current-kml-exact.mjs", "journey-explore-v2.js", "journey-nodo8.mjs",
    "journey-map-ready.mjs",
    "journey-premium.css",
]
preserved = json.loads((ROOT / BASE / "upstream-import.json").read_text(encoding="utf-8"))["preserved_assets"]
files = {
    "index.html", "favicon.svg", "styles.css", "app.js", "assets/nodo8-proposal.json",
    "nodo8-line.mjs", "nodo8-experience.mjs", "nodo8-experience.css",
    "nodo8-player.mjs", "nodo8-polish.css", "nodo8-stop-times.mjs",
    "nodo8-design.css", "nodo8-journey-inspector.mjs",
    "nodo8-coverage.mjs", "assets/nodo8-coverage-comparison.json",
    "nodo8-s8.mjs", "assets/nodo8-s8-simulation.json",
    "nodo8-current.mjs", "assets/nodo8-current-simulation.json",
    "docs/NODO8_CONFRONTO_D184_D185_E_RECAP_2026_10_07.md",
    "docs/RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md",
    "outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson",
    *[BASE + file for file in runtime],
    *[BASE + file["path"] for file in preserved],
}
policy = {
    "contract": "nodo8_final_only_publication_v1",
    "published_html_pages": ["index.html", "dietro-l-analisi/index.html"],
    "include_files": sorted(files),
    "semantics": "Excluded prototypes and source files remain in Git. Only this allowlist enters the Pages artifact.",
}
if __name__ == "__main__":
    (ROOT / "config/nodo8_publication_allowlist.json").write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(files)} final-site dependencies.")
