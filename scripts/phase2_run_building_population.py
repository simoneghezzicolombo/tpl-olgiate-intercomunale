#!/usr/bin/env python3
"""Canonical fail-closed entrypoint for Phase 2 building population.

The current official ISTAT 2023 regional package is identified from the package
contents, not from a guessed filename. Header/schema discovery inspects only the
first rows in read-only mode, then loads the selected table exactly once.
"""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
import sys
import zipfile

from openpyxl import load_workbook
import pandas as pd

import phase2_build_building_population as impl


SECTION_EXACT = (
    "SEZ21_ID", "SEZ2021_ID", "SEZIONE", "COD_SEZ", "SEZ23_ID", "SEZ_ID"
)
MUNICIPALITY_EXACT = (
    "PRO_COM", "PRO_COM_T", "COD_COM", "CODICE_COMUNE", "COD_COMUNE"
)
POPULATION_EXACT = (
    "P1", "POP2023", "POP23", "POP_TOT", "POP", "POPOLAZIONE"
)


def _single(items: list, label: str):
    if len(items) != 1:
        raise RuntimeError(f"expected exactly one {label}, got {items}")
    return items[0]


def _workbook_member(names: list[str]) -> str:
    # The URL itself fixes the release year. Do not require the provider to repeat
    # "2023" in the internal filename, which is not part of the data contract.
    preferred = [
        n for n in names
        if n.lower().endswith(".xlsx")
        and "r03" in n.lower()
        and "tracciato" not in n.lower()
        and ("sez" in n.lower() or "indicator" in n.lower())
    ]
    if len(preferred) == 1:
        return preferred[0]
    fallback = [
        n for n in names
        if n.lower().endswith(".xlsx")
        and "r03" in n.lower()
        and "tracciato" not in n.lower()
    ]
    return _single(fallback, "Lombardia regional section workbook in official 2023 package")


def _find_exact(columns, names):
    lookup = {str(c).strip().upper(): c for c in columns if c is not None}
    for name in names:
        if name in lookup:
            return lookup[name]
    return None


def _section_candidates(columns) -> list:
    exact = _find_exact(columns, SECTION_EXACT)
    if exact is not None:
        return [exact]
    out = []
    for c in columns:
        low = str(c).strip().lower()
        if "sez" in low and any(k in low for k in ("id", "cod", "2021", "21")):
            out.append(c)
    return out


def _municipality_candidates(columns) -> list:
    exact = _find_exact(columns, MUNICIPALITY_EXACT)
    if exact is not None:
        return [exact]
    out = []
    for c in columns:
        low = str(c).strip().lower()
        if "pro_com" in low or ("cod" in low and "com" in low):
            out.append(c)
    return out


def _population_candidates(columns) -> list:
    exact = _find_exact(columns, POPULATION_EXACT)
    if exact is not None:
        return [exact]
    out = []
    for c in columns:
        low = str(c).strip().lower()
        if "popol" in low and ("resident" in low or low == "popolazione"):
            out.append(c)
    return out


def _discover_table(raw: bytes) -> tuple[pd.DataFrame, str, int, object, object, object]:
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    matches = []
    observations = []
    try:
        for sheet in workbook.sheetnames:
            ws = workbook[sheet]
            for header in range(0, 11):
                values = next(
                    ws.iter_rows(min_row=header + 1, max_row=header + 1, values_only=True),
                    None,
                )
                if not values:
                    continue
                columns = list(values)
                sec = _section_candidates(columns)
                muni = _municipality_candidates(columns)
                pop = _population_candidates(columns)
                if sec or muni or pop:
                    observations.append({
                        "sheet": sheet,
                        "header": header,
                        "section": [str(v) for v in sec],
                        "municipality": [str(v) for v in muni],
                        "population": [str(v) for v in pop],
                    })
                if len(sec) == 1 and len(pop) == 1 and len(muni) == 1:
                    matches.append((sheet, header, sec[0], muni[0], pop[0]))
                    break
    finally:
        workbook.close()

    if len(matches) != 1:
        raise RuntimeError(
            "ISTAT 2023 workbook schema is not uniquely identifiable with an explicit municipal key; "
            f"matches={[(m[0], m[1], str(m[2]), str(m[3]), str(m[4])) for m in matches]}; "
            f"candidate_observations={observations[:30]}"
        )
    sheet, header, section_col, muni_col, pop_col = matches[0]
    df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, header=header, dtype=object, engine="openpyxl")
    return df, sheet, header, section_col, muni_col, pop_col


def load_istat_2023_sections(source_dir: Path, selected_codes: set[str]):
    zip_path = source_dir / "istat_sections_2023.zip"
    info = impl.download(impl.ISTAT_SECTIONS_2023_URL, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        member = _workbook_member(names)
        raw = z.read(member)

    df, sheet, header, section_col, muni_col, pop_col = _discover_table(raw)
    xlsx_path = source_dir / "R03_2023_sections_selected_source.xlsx"
    xlsx_path.write_bytes(raw)

    section_raw = df[section_col].astype(str)
    out = pd.DataFrame({
        "section_id_raw": section_raw,
        "section_id": df[section_col].map(impl.normalise_section),
        "municipality_code": df[muni_col].map(impl.normalise_municipality),
        "population_2023_fact": pd.to_numeric(df[pop_col], errors="coerce"),
    })
    out = out.loc[out["municipality_code"].isin(selected_codes)].copy()
    if out.empty:
        raise RuntimeError("no selected municipalities found in ISTAT 2023 section table")
    if out["population_2023_fact"].isna().any():
        bad = out.loc[out["population_2023_fact"].isna(), ["section_id_raw", "municipality_code"]].head(20)
        raise RuntimeError(f"non-numeric ISTAT 2023 population in selected rows: {bad.to_dict('records')}")
    if (out["population_2023_fact"] < 0).any():
        raise RuntimeError("negative ISTAT 2023 section population")
    if not out["population_2023_fact"].map(math.isfinite).all():
        raise RuntimeError("non-finite ISTAT 2023 section population")
    if out["section_id"].eq("").any():
        raise RuntimeError("blank section identifier in selected ISTAT 2023 rows")
    if out["section_id"].duplicated().any():
        dup = out.loc[out["section_id"].duplicated(keep=False), "section_id"].head(20).tolist()
        raise RuntimeError(f"duplicate ISTAT 2023 section IDs: {dup}")
    missing_muni = selected_codes - set(out["municipality_code"])
    if missing_muni:
        raise RuntimeError(f"selected municipalities absent from ISTAT 2023: {sorted(missing_muni)}")

    out["is_fictitious_section"] = out["section_id_raw"].map(impl.is_fictitious_section)
    out["population_2023_epistemic_status"] = "FACT_ISTAT_CENSUS_SECTION_2023"
    info.update({
        "epistemic_status": "FACT",
        "reference_year": 2023,
        "zip_member": member,
        "workbook_sheet": sheet,
        "header_row_zero_based": header,
        "regional_xlsx_sha256": hashlib.sha256(raw).hexdigest(),
        "regional_xlsx_bytes": len(raw),
        "section_id_field": str(section_col),
        "municipality_field_or_method": f"FACT_FIELD:{muni_col}",
        "population_field": str(pop_col),
        "selected_rows": len(out),
        "selected_fictitious_rows": int(out["is_fictitious_section"].sum()),
    })
    return out, info


impl.load_istat_2023_sections = load_istat_2023_sections

if __name__ == "__main__":
    sys.exit(impl.main())
