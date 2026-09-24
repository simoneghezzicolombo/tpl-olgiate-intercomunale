#!/usr/bin/env python3
"""Acquire the official ISTAT 2021 work-commuting OD matrix for Phase 2.

The official source is a direct ISTAT ZIP published through EsploraDati:
https://esploradati.istat.it/databrowser/DWL/PERMPOP/MATPEN/matrix_pendoLAVORO_2021.zip

The 2021 release contains work commuting only. It must not be presented as a
student-commuting matrix. This script keeps every OD row where either origin or
destination is one of the five core municipalities and writes a deterministic
canonical CSV plus summary/provenance outputs.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://esploradati.istat.it/databrowser/DWL/PERMPOP/MATPEN/"
    "matrix_pendoLAVORO_2021.zip"
)
SOURCE_PAGE = "https://www.istat.it/notizia/matrice-di-pendolarismo-per-lavoro/"
CORE = {
    "097010": "Brivio",
    "097012": "Calco",
    "097058": "Olgiate Molgora",
    "097074": "Santa Maria Hoè",
    "097092": "La Valletta Brianza",
}
OUT = ROOT / "data/raw/od/matrice_pendolarismo_istat_2021_core.csv"
SUMMARY = ROOT / "outputs/phase2/od_2021_core_summary.csv"
VALIDATION = ROOT / "outputs/phase2/od_2021_validation.json"
MANIFEST = ROOT / "data/manifest.csv"
DATASET_ID = "istat_matrice_pendolarismo_lavoro_2021_core"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise_code(value: str) -> str:
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if len(digits) == 5:
        digits = "0" + digits
    if len(digits) != 6:
        raise ValueError(f"invalid municipal code: {value!r}")
    return digits


def download_zip() -> bytes:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "tpl-olgiate-phase2/1.0 (+github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    if len(data) < 100_000 or data[:2] != b"PK":
        raise RuntimeError(f"ISTAT 2021 commuting download is not a plausible ZIP: {len(data)} bytes")
    return data


def extract_table(zip_bytes: bytes) -> tuple[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        candidates = [
            info for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith((".csv", ".txt"))
        ]
        if not candidates:
            raise RuntimeError(f"No CSV/TXT data file found in official ZIP: {archive.namelist()}")
        primary = max(candidates, key=lambda item: item.file_size)
        return primary.filename, archive.read(primary)


def decode_table(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise RuntimeError("Could not decode official ISTAT table")


def parse_rows(text: str) -> tuple[list[tuple[str, str, int]], dict]:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise RuntimeError("ISTAT table has no header")
    header = {name.strip().upper(): name for name in reader.fieldnames}

    def resolve(*aliases: str) -> str:
        for alias in aliases:
            if alias in header:
                return header[alias]
        raise RuntimeError(f"Missing required field {aliases}; actual header={list(header)}")

    origin_col = resolve("PROCOM_RES", "ITTER107_RES", "COD_RES", "ORIGINE")
    dest_col = resolve("PROCOM_LAV", "PROCOM_DEST", "ITTER107_DEST", "COD_DEST", "DESTINAZIONE")
    value_col = resolve("PENDOLARI", "OBS_VALUE", "VALUE", "STIMA", "NUMERO")

    all_rows = 0
    national_total = 0
    selected: list[tuple[str, str, int]] = []
    for row in reader:
        try:
            origin = normalise_code(row[origin_col])
            dest = normalise_code(row[dest_col])
            value = int(round(float(str(row[value_col]).strip().replace(",", "."))))
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        all_rows += 1
        national_total += value
        if origin in CORE or dest in CORE:
            selected.append((origin, dest, value))

    if not 450_000 <= all_rows <= 600_000:
        raise RuntimeError(f"Unexpected national OD row count: {all_rows}")
    if not 18_000_000 <= national_total <= 21_000_000:
        raise RuntimeError(f"Unexpected national commuter total: {national_total}")
    if not selected:
        raise RuntimeError("No core-municipality OD rows found")

    # The official 2021 matrix should have one record per municipality pair.
    aggregated: dict[tuple[str, str], int] = defaultdict(int)
    for origin, dest, value in selected:
        aggregated[(origin, dest)] += value
    canonical = [(o, d, aggregated[(o, d)]) for o, d in sorted(aggregated)]
    meta = {
        "delimiter": delimiter,
        "origin_column": origin_col,
        "destination_column": dest_col,
        "value_column": value_col,
        "national_positive_od_rows": all_rows,
        "national_commuters_sum": national_total,
        "selected_raw_rows": len(selected),
        "selected_unique_od_pairs": len(canonical),
    }
    return canonical, meta


def write_core(rows: list[tuple[str, str, int]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["procom_res", "procom_lav", "pendolari"])
        writer.writerows(rows)


def write_summary(rows: list[tuple[str, str, int]]) -> None:
    outbound = defaultdict(int)
    inbound = defaultdict(int)
    internal = defaultdict(int)
    destinations: dict[str, set[str]] = defaultdict(set)
    origins: dict[str, set[str]] = defaultdict(set)
    for origin, dest, value in rows:
        if origin in CORE:
            if origin == dest:
                internal[origin] += value
            else:
                outbound[origin] += value
                destinations[origin].add(dest)
        if dest in CORE and origin != dest:
            inbound[dest] += value
            origins[dest].add(origin)

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([
            "procom", "comune", "internal_workers", "outbound_workers", "inbound_workers",
            "resident_commuters", "self_containment_pct", "n_external_destinations", "n_external_origins",
        ])
        for code, name in CORE.items():
            resident = internal[code] + outbound[code]
            self_containment = (100.0 * internal[code] / resident) if resident else 0.0
            writer.writerow([
                code, name, internal[code], outbound[code], inbound[code], resident,
                f"{self_containment:.6f}", len(destinations[code]), len(origins[code]),
            ])


def update_manifest(source_zip_sha: str, source_member: str) -> None:
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise RuntimeError("manifest.csv has no header")
        rows = [row for row in reader if row["dataset_id"] != DATASET_ID]

    rows.append({
        "dataset_id": DATASET_ID,
        "ente_fonte": "ISTAT - Censimento permanente della popolazione",
        "url_ufficiale": SOURCE_URL,
        "data_accesso": date.today().isoformat(),
        "anno_riferimento": "2021",
        "licenza": "CC BY 3.0 IT",
        "filepath_locale": str(OUT.relative_to(ROOT)),
        "sha256_hash": sha256_path(OUT),
        "dimensione_bytes": str(OUT.stat().st_size),
        "stato_epistemico": "DERIVED",
        "trasformazioni": "Deterministic extraction of all positive OD pairs with origin or destination in the five core municipalities; canonical LF CSV; no synthetic expansion",
        "note_provenance": f"Official 2021 work-only commuting matrix; source page {SOURCE_PAGE}; source ZIP sha256={source_zip_sha}; source member={source_member}; 2011 matrix retained for historical comparison",
    })
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    zip_bytes = download_zip()
    source_zip_sha = sha256_bytes(zip_bytes)
    member_name, raw_table = extract_table(zip_bytes)
    rows, meta = parse_rows(decode_table(raw_table))
    write_core(rows)
    write_summary(rows)
    update_manifest(source_zip_sha, member_name)

    validation = {
        "source": "ISTAT Matrice di pendolarismo per lavoro 2021",
        "source_url": SOURCE_URL,
        "source_page": SOURCE_PAGE,
        "reference_date": "2021-12-31",
        "scope": "WORK_COMMUTING_ONLY",
        "core_codes": sorted(CORE),
        "source_zip_sha256": source_zip_sha,
        "source_member": member_name,
        "core_output": str(OUT.relative_to(ROOT)),
        "core_output_sha256": sha256_path(OUT),
        "core_output_bytes": OUT.stat().st_size,
        **meta,
    }
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
