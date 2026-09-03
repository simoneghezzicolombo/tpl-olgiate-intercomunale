from pathlib import Path

# Fix Gate B POSAS totals: POSAS includes ages 0..100 plus Età=999, where 999 is
# already the municipality total. Summing all rows double-counts population.
p = Path('scripts/audit_02_real_spatial.py')
s = p.read_text(encoding='utf-8')
old = '''def load_posas_totals() -> pd.DataFrame:\n    df = pd.read_csv(\n        POSAS,\n        sep=";",\n        skiprows=1,\n        dtype={"Codice comune": str},\n        encoding="utf-8-sig",\n        low_memory=False,\n    )\n    required = {"Codice comune", "Comune", "Totale"}\n    if not required.issubset(df.columns):\n        raise ValueError(f"POSAS schema changed; missing={required - set(df.columns)}")\n    df["Codice comune"] = (\n        df["Codice comune"].astype(str).str.replace(r"\\.0$", "", regex=True).str.zfill(6)\n    )\n    df["Totale"] = pd.to_numeric(df["Totale"], errors="coerce")\n    core = df[df["Codice comune"].isin(CORE_CODES)].copy()\n    totals = (\n        core.groupby(["Codice comune", "Comune"], as_index=False)["Totale"]\n        .sum()\n        .rename(columns={"Totale": "istat_2025"})\n    )\n    if len(totals) != 5 or totals["istat_2025"].isna().any():\n        raise ValueError(f"Could not derive all five POSAS totals: {totals}")\n    return totals\n'''
new = '''def load_posas_totals() -> pd.DataFrame:\n    df = pd.read_csv(\n        POSAS,\n        sep=";",\n        skiprows=1,\n        dtype={"Codice comune": str},\n        encoding="utf-8-sig",\n        low_memory=False,\n    )\n    required = {"Codice comune", "Comune", "Età", "Totale"}\n    if not required.issubset(df.columns):\n        raise ValueError(f"POSAS schema changed; missing={required - set(df.columns)}")\n    df["Codice comune"] = (\n        df["Codice comune"].astype(str).str.replace(r"\\.0$", "", regex=True).str.zfill(6)\n    )\n    df["Età_num"] = pd.to_numeric(df["Età"], errors="coerce")\n    df["Totale"] = pd.to_numeric(df["Totale"], errors="coerce")\n    core = df[df["Codice comune"].isin(CORE_CODES)].copy()\n\n    # ISTAT POSAS publishes one municipality aggregate row with Età=999.\n    # Ages 0..100 sum to that row; adding the 999 row to the age rows would\n    # double-count the population exactly. Use the official aggregate and\n    # independently verify it against the detailed age rows.\n    aggregate = core[core["Età_num"] == 999].copy()\n    if len(aggregate) != 5 or set(aggregate["Codice comune"]) != CORE_CODES:\n        raise ValueError(\n            "POSAS must contain exactly one Età=999 aggregate row for each core municipality"\n        )\n    if aggregate["Totale"].isna().any():\n        raise ValueError("POSAS Età=999 aggregate contains missing population totals")\n\n    detail = (\n        core[core["Età_num"].between(0, 100, inclusive="both")]\n        .groupby("Codice comune", as_index=False)["Totale"]\n        .sum()\n        .rename(columns={"Totale": "detail_sum"})\n    )\n    check = aggregate[["Codice comune", "Totale"]].merge(detail, on="Codice comune", how="left")\n    if check["detail_sum"].isna().any() or not np.allclose(\n        check["Totale"].to_numpy(dtype=float),\n        check["detail_sum"].to_numpy(dtype=float),\n        atol=1e-6,\n    ):\n        raise ValueError(f"POSAS age detail does not reconcile with Età=999 totals: {check}")\n\n    return (\n        aggregate[["Codice comune", "Comune", "Totale"]]\n        .rename(columns={"Totale": "istat_2025"})\n        .reset_index(drop=True)\n    )\n'''
if s.count(old) != 1:
    raise RuntimeError(f'load_posas_totals matcher count={s.count(old)}')
s = s.replace(old, new, 1)
old_note = '            "Population calibration is multiplicative within each official municipality and exactly quadrates to POSAS 2025 totals.",\n'
new_note = '            "Population calibration is multiplicative within each official municipality and exactly quadrates to the POSAS 2025 Età=999 official aggregate row; age-detail rows are independently reconciled to prevent double counting.",\n'
if s.count(old_note) != 1:
    raise RuntimeError(f'method note matcher count={s.count(old_note)}')
s = s.replace(old_note, new_note, 1)
p.write_text(s, encoding='utf-8')

# Align Gate B tests with the official POSAS aggregate semantics and add a regression test.
t = Path('tests/test_gate_b_spatial.py')
ts = t.read_text(encoding='utf-8')
ts = ts.replace(
    '    tobler_walk_minutes,\n)',
    '    load_posas_totals,\n    tobler_walk_minutes,\n)',
    1,
)
old_helper = '''def _posas_totals():\n    df = pd.read_csv(\n        POSAS,\n        sep=';',\n        skiprows=1,\n        dtype={'Codice comune': str},\n        encoding='utf-8-sig',\n        low_memory=False,\n    )\n    df['Codice comune'] = (\n        df['Codice comune'].astype(str).str.replace(r'\\.0$', '', regex=True).str.zfill(6)\n    )\n    df['Totale'] = pd.to_numeric(df['Totale'], errors='coerce')\n    return df[df['Codice comune'].isin(CORE_CODES)].groupby('Codice comune')['Totale'].sum()\n'''
new_helper = '''def _posas_totals():\n    df = pd.read_csv(\n        POSAS,\n        sep=';',\n        skiprows=1,\n        dtype={'Codice comune': str},\n        encoding='utf-8-sig',\n        low_memory=False,\n    )\n    df['Codice comune'] = (\n        df['Codice comune'].astype(str).str.replace(r'\\.0$', '', regex=True).str.zfill(6)\n    )\n    df['Età_num'] = pd.to_numeric(df['Età'], errors='coerce')\n    df['Totale'] = pd.to_numeric(df['Totale'], errors='coerce')\n    agg = df[df['Codice comune'].isin(CORE_CODES) & (df['Età_num'] == 999)].copy()\n    return agg.set_index('Codice comune')['Totale']\n'''
if ts.count(old_helper) != 1:
    raise RuntimeError(f'_posas_totals matcher count={ts.count(old_helper)}')
ts = ts.replace(old_helper, new_helper, 1)
anchor = '''def test_gate_b_source_contains_no_legacy_random_or_manual_nuclei():\n'''
regression = '''def test_posas_aggregate_row_is_not_double_counted():\n    parsed = load_posas_totals().set_index('Codice comune')['istat_2025'].sort_index()\n    official = _posas_totals().sort_index()\n    assert np.allclose(parsed.to_numpy(), official.to_numpy(), atol=1e-6)\n\n    raw = pd.read_csv(\n        POSAS, sep=';', skiprows=1, dtype={'Codice comune': str},\n        encoding='utf-8-sig', low_memory=False,\n    )\n    raw['Codice comune'] = raw['Codice comune'].astype(str).str.replace(r'\\.0$', '', regex=True).str.zfill(6)\n    raw['Età_num'] = pd.to_numeric(raw['Età'], errors='coerce')\n    raw['Totale'] = pd.to_numeric(raw['Totale'], errors='coerce')\n    core = raw[raw['Codice comune'].isin(CORE_CODES)]\n    naive = core.groupby('Codice comune')['Totale'].sum().sort_index()\n    # The old bug summed detailed ages plus the already-aggregated 999 row.\n    assert np.allclose(naive.to_numpy(), 2.0 * official.to_numpy(), atol=1e-6)\n    assert float(parsed.sum()) == 22914.0\n\n\n'''
if ts.count(anchor) != 1:
    raise RuntimeError(f'test insertion anchor count={ts.count(anchor)}')
ts = ts.replace(anchor, regression + anchor, 1)
t.write_text(ts, encoding='utf-8')

print('Applied POSAS Età=999 aggregate fix and regression coverage.')
