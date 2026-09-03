#!/usr/bin/env python3
"""Hardened Phase 2 building-population entrypoint.

ISTAT 2023 regional section workbooks expose PROCOM as the six-digit national
municipality code. This wrapper makes that official field the preferred
municipal key and validates it against the national SEZ21_ID structure before
allowing the production build to proceed.
"""
from __future__ import annotations

import sys

import phase2_run_building_population as previous


# Official ISTAT national municipality key. Keep legacy aliases only as
# fail-closed fallbacks for schema discovery, never ahead of PROCOM.
previous.MUNICIPALITY_EXACT = (
    "PROCOM",
    "PRO_COM",
    "PRO_COM_T",
    "COD_COM",
    "CODICE_COMUNE",
    "COD_COMUNE",
)

_original_loader = previous.load_istat_2023_sections


def _municipality_from_national_section_id(value: object) -> str:
    """Recover official PRO_COM from the 13-digit national SEZ21_ID.

    SEZ21_ID is defined by ISTAT as PRO_COM (6 digits) concatenated with the
    seven-digit within-municipality section code. Spreadsheet numeric typing
    may drop the leading zero, so the normalized value is left-padded to 13
    digits before extracting the municipality prefix.
    """
    section_id = previous.impl.normalise_section(value)
    if not section_id.isdigit() or len(section_id) > 13:
        raise RuntimeError(f"invalid national ISTAT SEZ21_ID: {value!r}")
    national = section_id.zfill(13)
    return national[:6]


def load_istat_2023_sections(source_dir, selected_codes):
    out, info = _original_loader(source_dir, selected_codes)
    derived = out["section_id"].map(_municipality_from_national_section_id)
    mismatch = derived.ne(out["municipality_code"])
    if mismatch.any():
        sample = out.loc[
            mismatch,
            ["section_id_raw", "section_id", "municipality_code"],
        ].head(20).copy()
        sample["municipality_from_section_id"] = derived.loc[mismatch].head(20).to_numpy()
        raise RuntimeError(
            "ISTAT 2023 PROCOM disagrees with SEZ21_ID national prefix: "
            f"{sample.to_dict('records')}"
        )
    info["municipality_field_or_method"] = (
        "FACT_FIELD:PROCOM; VALIDATED_AGAINST_SEZ21_ID_NATIONAL_PREFIX"
    )
    info["municipality_section_id_consistency"] = "PASS"
    return out, info


previous.impl.load_istat_2023_sections = load_istat_2023_sections


if __name__ == "__main__":
    sys.exit(previous.impl.main())
