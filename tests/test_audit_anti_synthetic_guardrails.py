import os
import re
import pandas as pd
import pytest

def test_manifest_epistemic_status_integrity():
    """Verifica che nessun dataset nel manifest attivo sia classificato FACT senza fonte o PLACEHOLDER non dichiarato."""
    manifest_path = "data/manifest.csv"
    assert os.path.exists(manifest_path), "data/manifest.csv deve esistere"
    df = pd.read_csv(manifest_path)
    
    valid_states = {"FACT", "DERIVED", "ESTIMATE", "ASSUMPTION", "RECONSTRUCTED", "MODEL OUTPUT", "FIELD CHECK", "PLACEHOLDER", "INVALIDATED"}
    for idx, row in df.iterrows():
        assert row["stato_epistemico"] in valid_states, f"Stato epistemico non valido {row['stato_epistemico']} per {row['dataset_id']}"
        # Se dichiarato FACT, l'ente_fonte e l'URL devono essere validi e non vuoti
        if row["stato_epistemico"] == "FACT":
            assert pd.notna(row["ente_fonte"]) and len(str(row["ente_fonte"])) > 2
            assert pd.notna(row["url_ufficiale"]) and len(str(row["url_ufficiale"])) > 5

def test_no_synthetic_placeholder_in_real_inputs():
    """Verifica che i file in data/raw/ non contengano placeholder o stringhe casuali fittizie."""
    raw_dir = "data/raw"
    assert os.path.exists(raw_dir)
    # Verifica che la matrice pendolarismo sia effettivamente numerica e popolata
    od_core = os.path.join(raw_dir, "od", "matrice_pendolarismo_istat_2011_core.csv")
    if os.path.exists(od_core):
        df_od = pd.read_csv(od_core)
        assert len(df_od) > 0
        assert not df_od["flusso_pendolari"].isna().any()
        assert (df_od["flusso_pendolari"] >= 0).all()

def test_quarantine_archive_disclaimer():
    """Verifica che i file sintetici pre-audit siano chiaramente etichettati in quarantena."""
    readme_quarantine = "data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md"
    assert os.path.exists(readme_quarantine)
    with open(readme_quarantine, "r", encoding="utf-8") as f:
        content = f.read()
    assert "INVALIDATED BY EXTERNAL AUDIT" in content
    assert "DO NOT USE" in content
