from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PRODUCTION_INPUTS = (
    "outputs/route_variants.csv",
    "outputs/service_simulation_scenarios.csv",
    "outputs/scenario_comparison.csv",
    "data/simulazione_scenari.json",
    "data/scenario0_tempi_percorsi.csv",
)


def gate_e_production_scripts():
    paths = [ROOT / "scripts" / "10_service_simulation.py"]
    paths.extend(sorted((ROOT / "scripts").glob("gate_e_*.py")))
    return paths


def test_gate_e_production_code_never_reads_invalidated_legacy_outputs():
    for path in gate_e_production_scripts():
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_PRODUCTION_INPUTS:
            assert forbidden not in text, f"{path.name} reintroduced INVALIDATED input {forbidden}"


def test_gate_e_scripts_do_not_use_numpy_random_or_random_module():
    for path in gate_e_production_scripts():
        text = path.read_text(encoding="utf-8")
        assert "np.random" not in text
        assert "numpy.random" not in text
        assert "import random" not in text
        assert "from random" not in text


def test_gate_e_scripts_do_not_embed_old_recommendation_language():
    forbidden = ("SOLUZIONE OTTIMALE", "Raccomandato", "saldo zero esatto", "neutralità economica esatta")
    for path in gate_e_production_scripts():
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
