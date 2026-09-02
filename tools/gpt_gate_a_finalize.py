#!/usr/bin/env python3
"""One-shot Gate A finalizer. Runs only after the full provenance pipeline."""
from pathlib import Path
import re
import subprocess

ROOT = Path(".")
DOCS = Path("docs/fonti.md")
STATUS = Path("AGENT_STATUS.md")
PASS_DOC = Path("docs/GATE_A_PASS.md")

VALIDATED_COMMIT = "019a12806af09d744f6f22032d980441ae60dc06"
FUNCTIONAL_FIX_COMMIT = "bcdb9713fdb984c1754ca881ece67357542d6a9a"
CI_RUN = "33695160621"
CI_JOB = "100462353597"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# 1) Bring human-readable provenance in sync with the code that passed CI.
docs = DOCS.read_text(encoding="utf-8")
docs = replace_once(
    docs,
    "Lo stato **Gate A PASS** può essere assegnato solo dopo l'esecuzione dei test locali e dei test\n"
    "di clean acquisition. Il documento non sostituisce `data/manifest.csv`, che resta il registro\n",
    "**Gate A è PASS** sulla base della clean acquisition indipendente registrata nel run GitHub Actions\n"
    f"`{CI_RUN}`. Il documento non sostituisce `data/manifest.csv`, che resta il registro\n",
    "Gate A header",
)
docs = replace_once(
    docs,
    "- Provider operativo: Overpass API con endpoint primario Kumi e fallback pubblici.\n",
    "- Provider operativo: Overpass API con endpoint primario `overpass.private.coffee` e fallback pubblici `overpass-api.de` e `maps.mail.ru`.\n",
    "OSM provider",
)
docs = replace_once(
    docs,
    "La funzione `fetch_sfr_from_socrata()` scarica entrambi, seleziona campagne di novembre feriale,\n"
    "armonizza i nomi stazione e `Saliti24H`, aggrega per anno e calcola `Indice_2019_100`.\n",
    "La funzione `fetch_sfr_from_socrata()` scarica entrambi. Per il dataset 2015-2023 usa le campagne\n"
    "di novembre, che la documentazione regionale descrive già come media del giorno feriale; per\n"
    "2024-2025 filtra esplicitamente `TipoGiorno = Feriale`. Poi armonizza i nomi stazione e\n"
    "`Saliti24H`, aggrega per anno e calcola `Indice_2019_100`.\n",
    "SFR filtering methodology",
)
docs = replace_once(
    docs,
    "Il cambio di sorgente/metodologia dal 2024 resta esplicito: non va nascosto quando si interpretano\n"
    "variazioni nella serie temporale.\n",
    "Il cambio di sorgente e metodologia resta esplicito. Regione Lombardia segnala inoltre che dal 2023\n"
    "la misurazione passa ai contatori automatici e i livelli non sono necessariamente confrontabili in\n"
    "modo diretto con le precedenti rilevazioni manuali. Le variazioni 2019-2025 non vanno quindi lette\n"
    "come pura crescita della domanda senza questa cautela metodologica.\n",
    "SFR comparability caveat",
)
docs = replace_once(
    docs,
    "Gate B/C/D/E/F restano bloccati finché Gate A non riceve un PASS esterno.\n",
    "### Esito\n\n"
    f"**PASS.** Run GitHub Actions `{CI_RUN}`, job `{CI_JOB}`: pipeline completa ricostruita da clone pulito, "
    "16/16 test offline superati e 3/3 test di acquisizione reale via rete superati senza skip. "
    "Gate B è sbloccato; Gate C/D/E/F restano soggetti ai rispettivi checkpoint.\n",
    "Gate A outcome",
)
DOCS.write_text(docs, encoding="utf-8")

# 2) Create an explicit review record, separate from the general source catalogue.
trigger_commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], text=True
).strip()
PASS_DOC.write_text(
    f"""# Gate A — Provenance: PASS

**Verdetto:** PASS  
**Data:** 2026-09-03  
**Branch:** `antigravity-real-data`  
**Functional fix:** `{FUNCTIONAL_FIX_COMMIT}`  
**Validated commit:** `{VALIDATED_COMMIT}`  
**Finalization trigger:** `{trigger_commit}`  
**GitHub Actions run:** `{CI_RUN}`  
**Job:** `{CI_JOB}`

## Evidenza di validazione

Il Gate A non è stato approvato sulla base della sola presenza dei file nel repository. La validazione è stata eseguita su un runner Ubuntu pulito e ha richiesto alla pipeline di ricostruire il workspace a partire dal clone.

Risultati osservati nel run `{CI_RUN}`:

- compilazione di `scripts/audit_01_fetch_real_inputs.py`: PASS;
- test deterministici di rebuild POSAS e SFR: 2/2 PASS;
- `python scripts/audit_01_fetch_real_inputs.py` da clone pulito: PASS;
- manifest prodotto: 18 dataset attivi;
- suite Gate A offline dopo l'acquisizione: **16/16 PASS**;
- clean acquisition POSAS da ISTAT: PASS;
- clean acquisition SFR dai due dataset Regione Lombardia: PASS;
- clean acquisition OSM da Overpass: PASS;
- test di rete complessivi: **3/3 PASS, nessuno skip**.

## Provenance risolta

### ISTAT POSAS 2025

La provincia di Lecco viene ricostruita automaticamente dall'archivio ufficiale:
`https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip`.
Il file provinciale di progetto è quindi `DERIVED`, non una dipendenza manuale.

### Frequentazione SFR 2015-2025

La serie deriva da due dataset ufficiali Regione Lombardia:

- `m2u2-frtq`, storico 2015-2023;
- `ut63-s688`, recente 2024-2025.

Per il 2015-2023 la fonte è già riferita al giorno feriale medio. Dal 2024 il tipo di giorno è presente nel dataset e la pipeline filtra esplicitamente il feriale. La documentazione regionale segnala inoltre una discontinuità metodologica con l'introduzione dei contatori automatici dal 2023: confronti temporali che attraversano il cambio di metodo devono essere interpretati con cautela.

### OpenStreetMap

L'acquisizione usa query Overpass esplicite e mirror pubblici con fallback. Un fetch live OSM è per natura time-varying, quindi la riproducibilità non viene definita come identità eterna del risultato live, ma come combinazione di query/processo documentati, data di accesso e checksum dello snapshot raw utilizzato nell'audit. Le fermate OSM restano un cross-check; `stops.txt` del GTFS Agenzia è la fonte istituzionale primaria per il TPL.

## Conseguenza

**Gate B — real spatial integrity è sbloccato.** Nessun risultato di routing o raccomandazione viene tuttavia promosso finché non supererà i Gate B, C, D ed E applicabili.
""",
    encoding="utf-8",
)

# 3) Replace the stale current-status snapshot while retaining historical handoffs below.
status = STATUS.read_text(encoding="utf-8")
new_snapshot = f"""## Stato corrente

**Data:** 2026-09-03  
**Autore:** GPT external reviewer / co-developer  
**Branch:** `antigravity-real-data`  
**Gate A:** **PASS**  
**Commit funzionale Gate A:** `{FUNCTIONAL_FIX_COMMIT}`  
**Commit validato:** `{VALIDATED_COMMIT}`  
**CI:** run `{CI_RUN}`, job `{CI_JOB}`  
**Risultati:** clean rebuild completo PASS, 16/16 test offline PASS, 3/3 clean-network PASS  
**Prossimo checkpoint:** `AUDIT_CHECKPOINT_2_REAL_SPATIAL` (Gate B)  

`docs/GATE_A_PASS.md` è il verbale autorevole del verdetto. Gli handoff Antigravity sottostanti restano conservati come cronologia e non prevalgono sullo stato corrente.

---

"""
status, n = re.subn(
    r"## Stato corrente\n.*?\n---\n\n(?=## Handoff)",
    new_snapshot,
    status,
    count=1,
    flags=re.S,
)
if n != 1:
    raise RuntimeError(f"AGENT_STATUS current snapshot replacement count={n}")
STATUS.write_text(status, encoding="utf-8")

# 4) Remove the one-shot tooling used only to make these remote edits safely.
for rel in [
    ".github/workflows/gpt-gate-a-autofix.yml",
    "tools/gpt_gate_a_autofix.py",
    "tools/gpt_gate_a_autofix_2.py",
    "tools/gpt_gate_a_finalize.py",
]:
    p = Path(rel)
    if p.exists():
        p.unlink()

print("Gate A finalization snapshot prepared; temporary GPT patch tooling removed.")
