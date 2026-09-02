"""
tests/test_outputs_non_empty.py
Verifica che tutti gli output richiesti dal progetto (CSV, mappe HTML, grafici PNG, documentazione MD)
esistano e abbiano contenuto non vuoto.
"""

import os
import pytest

OUTPUT_FILES = [
    # Baseline
    "outputs/current_service_baseline.csv",
    # Grid e accessibilità
    "data/processed/population_grid_calibrated.csv",
    "data/processed/demografia_comunale_istat_2025.csv",
    "data/processed/walk_isochrones_cells.csv",
    "outputs/stop_analysis.csv",
    "outputs/fraction_analysis.csv",
    # OD e POI
    "outputs/od_matrix_core.csv",
    "data/processed/poi_dataset.csv",
    "outputs/poi_summary_by_category.csv",
    # Varianti e idoneità
    "outputs/route_variants.csv",
    "outputs/field_checks.csv",
    "outputs/deviation_efficiency.csv",
    # Pareto e simulazione
    "outputs/pareto_frontier.csv",
    "outputs/service_simulation_scenarios.csv",
    "outputs/train_connections.csv",
    "outputs/scenario_comparison.csv",
    # Mappe
    "outputs/maps/mappa_interattiva_rete_tpl_olgiate.html",
    # Grafici
    "outputs/figures/01_residenti_serviti_per_scenario.png",
    "outputs/figures/02_bus_km_annui_per_scenario.png",
    "outputs/figures/03_pareto_coverage_vs_runtime.png",
    "outputs/figures/04_rendimento_deviazioni_frazioni.png",
    "outputs/figures/05_copertura_demografica_per_comune.png",
    "outputs/figures/06_matrice_od_destinazioni.png",
    # Questionario
    "survey/questionario.md",
    "survey/questionario_schema.csv",
    "survey/privacy_note.md",
    # Documentazione
    "docs/metodologia.md",
    "docs/fonti.md",
    "docs/risultati_preliminari.md",
    "docs/rapporto_finale.md",
    "docs/limiti.md"
]

@pytest.mark.parametrize("fpath", OUTPUT_FILES)
def test_output_file_exists_and_non_empty(fpath):
    assert os.path.exists(fpath), f"File atteso non trovato: {fpath}"
    file_size = os.path.getsize(fpath)
    assert file_size > 0, f"File {fpath} è vuoto (0 byte)!"
