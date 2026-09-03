#!/usr/bin/env python3
"""Canonical fail-closed entrypoint for Phase 2 building population.

The underlying production module predates observation of the current ISTAT 2023
regional workbook packaging. This entrypoint replaces only that input reader with
schema discovery that must identify one workbook, one sheet/header and one set of
section/population keys before delegating to the deterministic production build.
"""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
import sys
import zipfile

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
    preferred = [
        n for n in names
        if n.lower().endswith(".xlsx")
        and "r03" in n.lower()
        and "2023" in n.lower()
        and "tracciato" not in n.lower()
        and ("sez" in n.lower() or "indicator" in n.lower())
    ]
    if len(preferred) == 1:
        return preferred[0]
    fallback = [
        n for n in names
        if n.lower().endswith(".xlsx")
        and "r03" in n.lower()
        and "2023" in n.lower()
        and "tracciato" not in n.lower()
    ]
    return _single(fallback, "Lombardia 2023 regional workbook")


def _find_exact(columns, names):
    lookup = {str(c).strip().upper(): c for c in columns}
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


def _discover_table(raw: bytes) -> tuple[pd.DataFrame, str, int, object, object | None, object]:
    xls = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
    matches = []
    observations = []
    for sheet in xls.sheet_names:
        for header in range(0, 11):
            df = pd.read_excel(xls, sheet_name=sheet, header=header, dtype=object)
            if df.empty:
                continue
            sec = _section_candidates(df.columns)
            muni = _municipality_candidates(df.columns)
            pop = _population_candidates(df.columns)
            observations.append({
                "sheet": sheet,
                "header": header,
                "section": [str(v) for v in sec],
                "municipality": [str(v) for v in muni],
                "population": [str(v) for v in pop],
            })
            if len(sec) == 1 and len(pop) == 1 and len(muni) <= 1:
                matches.append((df, sheet, header, sec[0], muni[0] if muni else None, pop[0]))
                break
    if len(matches) != 1:
        compact = [o for o in observations if o["section"] or o["population"]]
        raise RuntimeError(
            "ISTAT 2023 workbook schema is not uniquely identifiable; "
            f"matches={[(m[1], m[2], str(m[3]), str(m[4]), str(m[5])) for m in matches]}; "
            f"candidate_observations={compact[:30]}"
        )
    return matches[0]


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
        "population_2023_fact": pd.to_numeric(df[pop_col], errors="coerce"),
    })
    if muni_col is not None:
        out["municipality_code"] = df[muni_col].map(impl.normalise_municipality)
        municipality_method = f"FACT_FIELD:{muni_col}"
    else:
        # SEZ21_ID is the official unique census-section identifier. Deriving the
        # six-digit municipal prefix is deterministic, but explicitly DERIVED.
        raw_digits = section_raw.str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
        if (raw_digits.str.len() < 6).any():
            raise RuntimeError("cannot derive municipality from malformed official section identifier")
        out["municipality_code"] = raw_digits.str[:6]
        municipality_method = "DERIVED_FROM_OFFICIAL_SECTION_ID_FIRST_6_DIGITS"

    # Remove fully blank/footer rows before validating the actual section table.
    blank = out["section_id"].eq("") & out["population_2023_fact"].isna()
    out = out.loc[~blank].copy()
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
        "municipality_field_or_method": municipality_method,
        "population_field": str(pop_col),
        "selected_rows": len(out),
        "selected_fictitious_rows": int(out["is_fictitious_section"].sum()),
    })
    return out, info


impl.load_istat_2023_sections = load_istat_2023_sections

if __name__ == "__main__":
    sys.exit(impl.main())
