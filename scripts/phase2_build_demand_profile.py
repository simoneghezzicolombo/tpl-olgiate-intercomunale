#!/usr/bin/env python3
"""Build the audited Phase 2 demand profile from ISTAT 2021 work commuting.

This script deliberately does not use the 2011 extract for trend calculations. The
2011 source has additional census dimensions and needs a separate normalization
audit before totals can be compared safely with the one-row-per-OD 2021 release.

Outputs classify resident work destinations for the five core municipalities into:
- SELF: same municipality;
- OTHER_CORE: another municipality in the five-municipality study area;
- S8_DIRECT: an external municipality that physically contains an official S8 stop;
- OTHER_EXTERNAL: all other work destinations.

`S8_DIRECT` is a conservative infrastructure-addressability label, not an observed
modal-choice estimate. It says that the destination municipality lies directly on
the official S8 line. It does not imply that every worker can or will use rail, and
it excludes destinations that may be reachable with a rail or bus transfer.
"""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OD_2021 = ROOT / "data/raw/od/matrice_pendolarismo_istat_2021_core.csv"
GTFS = ROOT / "data/raw/gtfs/rail_trenord"
OUT_DIR = ROOT / "outputs/phase2"
DOC = ROOT / "docs/PHASE2_DEMAND_PROFILE_2021.md"

BOUNDARIES_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "non_generalizzati/2026/Limiti01012026.zip"
)
HEADERS = {
    "User-Agent": (
        "tpl-olgiate-phase2/1.0 "
        "(+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
    )
}
CORE = OrderedDict(
    [
        ("097010", "Brivio"),
        ("097012", "Calco"),
        ("097058", "Olgiate Molgora"),
        ("097074", "Santa Maria Hoè"),
        ("097092", "La Valletta Brianza"),
    ]
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_code(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 5:
        digits = "0" + digits
    return digits.zfill(6) if digits else ""


def download_national_municipalities() -> gpd.GeoDataFrame:
    """Download the validated 2026 ISTAT boundary source and return all municipalities."""
    response = requests.get(BOUNDARIES_URL, headers=HEADERS, timeout=180)
    response.raise_for_status()
    payload = response.content
    if len(payload) < 1_000_000 or payload[:2] != b"PK":
        raise RuntimeError(f"ISTAT boundaries download is not a plausible ZIP: {len(payload)} bytes")

    with tempfile.TemporaryDirectory(prefix="phase2_istat_comuni_") as tmp:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            shapefiles = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".shp") and "com" in Path(name).name.lower()
            ]
            preferred = [name for name in shapefiles if "wgs84" in name.lower()]
            if preferred:
                target = preferred[0]
            elif shapefiles:
                target = shapefiles[0]
            else:
                raise RuntimeError("No municipal shapefile found in official ISTAT boundaries ZIP")
            stem = str(Path(target).with_suffix(""))
            members = [name for name in archive.namelist() if str(Path(name).with_suffix("")) == stem]
            archive.extractall(tmp, members)
        shp = Path(tmp) / target
        municipalities = gpd.read_file(shp)

    if "PRO_COM_T" not in municipalities.columns or "COMUNE" not in municipalities.columns:
        raise RuntimeError(f"Unexpected ISTAT municipality schema: {list(municipalities.columns)}")
    municipalities = municipalities[["PRO_COM_T", "COMUNE", "geometry"]].copy()
    municipalities["procom"] = municipalities["PRO_COM_T"].map(normalize_code)
    municipalities["comune"] = municipalities["COMUNE"].astype(str).str.strip()
    municipalities = municipalities.drop(columns=["PRO_COM_T", "COMUNE"])
    municipalities = municipalities[municipalities["procom"].str.len() == 6].copy()
    if municipalities.crs is None:
        raise RuntimeError("ISTAT national municipality layer has no CRS")
    return municipalities.to_crs(4326)


def read_gtfs_s8_stops(municipalities: gpd.GeoDataFrame) -> pd.DataFrame:
    routes = pd.read_csv(GTFS / "routes.txt", dtype=str)
    trips = pd.read_csv(GTFS / "trips.txt", dtype=str, usecols=["route_id", "trip_id"])
    stop_times = pd.read_csv(GTFS / "stop_times.txt", dtype=str, usecols=["trip_id", "stop_id"])
    stops = pd.read_csv(
        GTFS / "stops.txt",
        dtype=str,
        usecols=lambda col: col in {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    )

    short = routes.get("route_short_name", pd.Series("", index=routes.index)).fillna("").str.upper().str.strip()
    s8_route_ids = set(routes.loc[short == "S8", "route_id"].astype(str))
    if not s8_route_ids:
        raise RuntimeError("Official Trenord GTFS contains no route_short_name=S8")
    s8_trip_ids = set(trips.loc[trips["route_id"].isin(s8_route_ids), "trip_id"].astype(str))
    if not s8_trip_ids:
        raise RuntimeError("No S8 trips found in official Trenord GTFS")
    s8_stop_ids = set(stop_times.loc[stop_times["trip_id"].isin(s8_trip_ids), "stop_id"].astype(str))
    s8 = stops[stops["stop_id"].isin(s8_stop_ids)].copy()
    s8["stop_lat"] = pd.to_numeric(s8["stop_lat"], errors="coerce")
    s8["stop_lon"] = pd.to_numeric(s8["stop_lon"], errors="coerce")
    s8 = s8.dropna(subset=["stop_lat", "stop_lon"]).copy()
    if s8.empty:
        raise RuntimeError("S8 stop set has no usable coordinates")

    points = gpd.GeoDataFrame(
        s8,
        geometry=gpd.points_from_xy(s8["stop_lon"], s8["stop_lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        points,
        municipalities[["procom", "comune", "geometry"]],
        how="left",
        predicate="within",
    )

    # A station point should normally fall inside a polygon. If a GTFS point is on a
    # municipal boundary, resolve it to the nearest municipality within 750 m rather
    # than hard-code a municipality name.
    missing_mask = joined["procom"].isna()
    if missing_mask.any():
        missing_points = joined.loc[missing_mask, ["stop_id", "geometry"]].copy()
        missing_points = gpd.GeoDataFrame(missing_points, geometry="geometry", crs=4326).to_crs(32632)
        mun_metric = municipalities[["procom", "comune", "geometry"]].to_crs(32632)
        nearest = gpd.sjoin_nearest(
            missing_points,
            mun_metric,
            how="left",
            max_distance=750,
            distance_col="boundary_distance_m",
        )
        nearest = nearest.sort_values("boundary_distance_m").drop_duplicates("stop_id")
        nearest_map = nearest.set_index("stop_id")[["procom", "comune"]].to_dict("index")
        for idx in joined.index[missing_mask]:
            stop_id = joined.at[idx, "stop_id"]
            match = nearest_map.get(stop_id)
            if match:
                joined.at[idx, "procom"] = match["procom"]
                joined.at[idx, "comune"] = match["comune"]

    if joined["procom"].isna().any():
        unresolved = joined.loc[joined["procom"].isna(), ["stop_id", "stop_name"]].to_dict("records")
        raise RuntimeError(f"Could not map S8 stops to ISTAT municipalities: {unresolved}")

    out = joined[["stop_id", "stop_name", "stop_lat", "stop_lon", "procom", "comune"]].copy()
    out["stop_name"] = out["stop_name"].astype(str).str.strip()
    out = out.drop_duplicates(subset=["stop_id", "procom"]).sort_values(["comune", "stop_name", "stop_id"])
    return out.reset_index(drop=True)


def code_name_map(municipalities: gpd.GeoDataFrame) -> dict[str, str]:
    mapping = dict(zip(municipalities["procom"].astype(str), municipalities["comune"].astype(str)))
    mapping.update(CORE)
    return mapping


def name_for(code: str, mapping: dict[str, str]) -> str:
    return mapping.get(code, f"ISTAT code {code} (not mapped in 2026 boundaries)")


def classify_destination(origin: str, dest: str, s8_municipalities: set[str]) -> str:
    if origin == dest:
        return "SELF"
    if dest in CORE:
        return "OTHER_CORE"
    if dest in s8_municipalities:
        return "S8_DIRECT"
    return "OTHER_EXTERNAL"


def classify_aggregate_destination(dest: str, s8_municipalities: set[str]) -> str:
    if dest in CORE:
        return "CORE_LOCAL"
    if dest in s8_municipalities:
        return "S8_DIRECT"
    return "OTHER_EXTERNAL"


def build_profiles(
    od: pd.DataFrame,
    names: dict[str, str],
    s8_municipalities: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resident = od[od["procom_res"].isin(CORE)].copy()
    if set(resident["procom_res"].unique()) != set(CORE):
        raise RuntimeError("Resident OD profile does not contain all five core municipalities")

    resident["origin_name"] = resident["procom_res"].map(lambda x: name_for(x, names))
    resident["destination_name"] = resident["procom_lav"].map(lambda x: name_for(x, names))
    resident["category"] = [
        classify_destination(o, d, s8_municipalities)
        for o, d in zip(resident["procom_res"], resident["procom_lav"])
    ]
    resident["origin_total"] = resident.groupby("procom_res")["pendolari"].transform("sum")
    resident["share_of_origin_pct"] = resident["pendolari"] / resident["origin_total"] * 100.0
    resident = resident.sort_values(["procom_res", "pendolari", "destination_name"], ascending=[True, False, True])
    resident["rank"] = resident.groupby("procom_res").cumcount() + 1
    resident["cumulative_share_pct"] = resident.groupby("procom_res")["share_of_origin_pct"].cumsum()
    resident = resident[
        [
            "procom_res",
            "origin_name",
            "procom_lav",
            "destination_name",
            "pendolari",
            "rank",
            "category",
            "share_of_origin_pct",
            "cumulative_share_pct",
        ]
    ].rename(columns={"pendolari": "workers"})

    aggregate = (
        resident.groupby(["procom_lav", "destination_name"], as_index=False)
        .agg(workers=("workers", "sum"), n_core_origins=("procom_res", "nunique"))
        .sort_values(["workers", "destination_name"], ascending=[False, True])
    )
    total = int(aggregate["workers"].sum())
    aggregate["rank"] = range(1, len(aggregate) + 1)
    aggregate["category"] = aggregate["procom_lav"].map(
        lambda d: classify_aggregate_destination(d, s8_municipalities)
    )
    aggregate["share_of_core_resident_workers_pct"] = aggregate["workers"] / total * 100.0
    aggregate["cumulative_share_pct"] = aggregate["share_of_core_resident_workers_pct"].cumsum()
    aggregate = aggregate[
        [
            "procom_lav",
            "destination_name",
            "workers",
            "n_core_origins",
            "rank",
            "category",
            "share_of_core_resident_workers_pct",
            "cumulative_share_pct",
        ]
    ]

    categories = ["SELF", "OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL"]
    rows: list[dict] = []
    for code, commune in CORE.items():
        part = resident[resident["procom_res"] == code]
        row: dict[str, object] = {
            "procom": code,
            "comune": commune,
            "resident_workers": int(part["workers"].sum()),
        }
        for cat in categories:
            value = int(part.loc[part["category"] == cat, "workers"].sum())
            row[f"{cat.lower()}_workers"] = value
            row[f"{cat.lower()}_pct"] = 100.0 * value / int(row["resident_workers"])
        row["core_local_workers"] = int(row["self_workers"]) + int(row["other_core_workers"])
        row["core_local_pct"] = 100.0 * int(row["core_local_workers"]) / int(row["resident_workers"])
        row["external_workers"] = int(row["s8_direct_workers"]) + int(row["other_external_workers"])
        row["external_pct"] = 100.0 * int(row["external_workers"]) / int(row["resident_workers"])
        rows.append(row)

    all_row: dict[str, object] = {
        "procom": "ALL_CORE",
        "comune": "Five core municipalities",
        "resident_workers": sum(int(row["resident_workers"]) for row in rows),
    }
    for cat in categories:
        value = sum(int(row[f"{cat.lower()}_workers"]) for row in rows)
        all_row[f"{cat.lower()}_workers"] = value
        all_row[f"{cat.lower()}_pct"] = 100.0 * value / int(all_row["resident_workers"])
    all_row["core_local_workers"] = int(all_row["self_workers"]) + int(all_row["other_core_workers"])
    all_row["core_local_pct"] = 100.0 * int(all_row["core_local_workers"]) / int(all_row["resident_workers"])
    all_row["external_workers"] = int(all_row["s8_direct_workers"]) + int(all_row["other_external_workers"])
    all_row["external_pct"] = 100.0 * int(all_row["external_workers"]) / int(all_row["resident_workers"])
    rows.append(all_row)
    corridor = pd.DataFrame(rows)

    inbound = od[od["procom_lav"].isin(CORE)].copy()
    inbound["destination_name"] = inbound["procom_lav"].map(CORE)
    inbound["origin_name"] = inbound["procom_res"].map(lambda x: name_for(x, names))
    inbound["origin_category"] = inbound["procom_res"].map(
        lambda origin: "CORE_LOCAL_ORIGIN"
        if origin in CORE
        else ("S8_DIRECT_ORIGIN" if origin in s8_municipalities else "OTHER_EXTERNAL_ORIGIN")
    )
    inbound["destination_total"] = inbound.groupby("procom_lav")["pendolari"].transform("sum")
    inbound["share_of_destination_workers_pct"] = inbound["pendolari"] / inbound["destination_total"] * 100.0
    inbound = inbound.sort_values(["procom_lav", "pendolari", "origin_name"], ascending=[True, False, True])
    inbound["rank"] = inbound.groupby("procom_lav").cumcount() + 1
    inbound = inbound[
        [
            "procom_lav",
            "destination_name",
            "procom_res",
            "origin_name",
            "pendolari",
            "rank",
            "origin_category",
            "share_of_destination_workers_pct",
        ]
    ].rename(columns={"pendolari": "workers"})
    return resident.reset_index(drop=True), aggregate.reset_index(drop=True), corridor, inbound.reset_index(drop=True)


def fmt(value: object, decimals: int = 1) -> str:
    if isinstance(value, (float, int)):
        return f"{float(value):.{decimals}f}"
    return str(value)


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def write_doc(
    resident: pd.DataFrame,
    aggregate: pd.DataFrame,
    corridor: pd.DataFrame,
    inbound: pd.DataFrame,
    s8_stops: pd.DataFrame,
    unmatched_codes: list[str],
) -> None:
    all_core = corridor[corridor["procom"] == "ALL_CORE"].iloc[0]
    lines = [
        "# Phase 2 — Profilo della domanda pendolare per lavoro 2021",
        "",
        "**Fonte domanda:** ISTAT, Matrice di pendolarismo per lavoro 2021.  ",
        "**Ambito:** residenti e lavoratori collegati a Brivio, Calco, Olgiate Molgora, Santa Maria Hoè e La Valletta Brianza.  ",
        "**Uso:** input di domanda osservata per la Phase 2 service-design optimisation.",
        "",
        "## Lettura corretta",
        "",
        "La matrice 2021 misura pendolarismo **per lavoro**. Non è una matrice di mobilità totale e non contiene una OD studenti completa. I viaggi per scuola, sanità, acquisti, servizi e tempo libero devono restare separati finché non esistono pesi empirici verificati.",
        "",
        "La categoria `S8_DIRECT` è una misura conservativa di **addressability infrastrutturale**: la destinazione lavorativa è un comune che contiene almeno una fermata della S8 ricavata dal GTFS ufficiale Trenord. Non è una stima della quota modale ferroviaria e non implica che ogni lavoratore abbia una destinazione finale raggiungibile a piedi dalla stazione. Destinazioni raggiungibili con cambio ferroviario o bus non sono incluse in questa categoria.",
        "",
        "## Quadro complessivo",
        "",
        f"I cinque comuni generano **{int(all_core['resident_workers']):,}** pendolari residenti per lavoro. Di questi **{int(all_core['self_workers']):,}** lavorano nello stesso comune di residenza, **{int(all_core['other_core_workers']):,}** in un altro dei cinque comuni, **{int(all_core['s8_direct_workers']):,}** in un comune esterno direttamente sulla S8 e **{int(all_core['other_external_workers']):,}** in altre destinazioni esterne.".replace(",", "."),
        "",
    ]
    summary_rows = []
    for _, row in corridor.iterrows():
        if row["procom"] == "ALL_CORE":
            continue
        summary_rows.append(
            [
                row["comune"],
                int(row["resident_workers"]),
                f"{row['core_local_pct']:.1f}%",
                f"{row['s8_direct_pct']:.1f}%",
                f"{row['other_external_pct']:.1f}%",
            ]
        )
    summary_rows.append(
        [
            "Totale 5 comuni",
            int(all_core["resident_workers"]),
            f"{all_core['core_local_pct']:.1f}%",
            f"{all_core['s8_direct_pct']:.1f}%",
            f"{all_core['other_external_pct']:.1f}%",
        ]
    )
    lines += [
        markdown_table(
            ["Origine", "Pendolari residenti", "Lavoro nei 5 comuni", "Destinazione S8 diretta", "Altra destinazione esterna"],
            summary_rows,
        ),
        "",
        "## Destinazioni aggregate principali",
        "",
    ]
    top = aggregate.head(20)
    lines.append(
        markdown_table(
            ["Rank", "Destinazione", "Lavoratori", "Quota", "Categoria"],
            [
                [int(r["rank"]), r["destination_name"], int(r["workers"]), f"{r['share_of_core_resident_workers_pct']:.1f}%", r["category"]]
                for _, r in top.iterrows()
            ],
        )
    )
    for code, commune in CORE.items():
        lines += ["", f"## Top destinazioni da {commune}", ""]
        part = resident[resident["procom_res"] == code].head(12)
        lines.append(
            markdown_table(
                ["Rank", "Destinazione", "Lavoratori", "Quota", "Categoria"],
                [
                    [int(r["rank"]), r["destination_name"], int(r["workers"]), f"{r['share_of_origin_pct']:.1f}%", r["category"]]
                    for _, r in part.iterrows()
                ],
            )
        )

    lines += ["", "## Domanda in ingresso nei cinque comuni", ""]
    inbound_totals = (
        inbound.groupby(["procom_lav", "destination_name"], as_index=False)["workers"]
        .sum()
        .sort_values("workers", ascending=False)
    )
    lines.append(
        markdown_table(
            ["Comune di lavoro", "Lavoratori totali con origine osservata"],
            [[r["destination_name"], int(r["workers"])] for _, r in inbound_totals.iterrows()],
        )
    )

    s8_unique = s8_stops[["procom", "comune"]].drop_duplicates().sort_values("comune")
    lines += ["", "## Comuni classificati come S8 diretti", ""]
    lines.append(
        markdown_table(
            ["Codice ISTAT", "Comune"],
            [[r["procom"], r["comune"]] for _, r in s8_unique.iterrows()],
        )
    )

    lines += [
        "",
        "## Nota sul confronto 2011 → 2021",
        "",
        "Il confronto storico **non viene ancora calcolato** in questo output. L'estrazione 2011 presente nel repository conserva dimensioni censuarie aggiuntive e mostra record che non possono essere sommati in sicurezza senza ricostruire il tracciato e le categorie originali. La 2021, invece, è già normalizzata a una coppia comune-origine → comune-destinazione. Il confronto sarà aggiunto solo dopo un audit dedicato della 2011, così da evitare doppi conteggi o confronti tra universi diversi.",
        "",
        "## Implicazione per il service design",
        "",
        "Questi dati non autorizzano da soli a scegliere una linea. Servono a pesare la domanda lavorativa osservata. La Phase 2 deve combinare questa evidenza con popolazione, walking access, poli verificati, rete bus esistente, tempi stradali, S8, frequenza, affidabilità e vincolo di produzione. In particolare, `S8_DIRECT` fornisce un **lower bound interpretabile** della domanda per cui un feeder efficace verso Olgiate-Calco-Brivio FS può offrire una catena di viaggio ferroviaria diretta verso il comune di lavoro.",
        "",
    ]
    if unmatched_codes:
        lines += [
            "### Codici OD non risolti con i confini comunali 2026",
            "",
            "Alcuni codici presenti nella matrice 2021 non hanno una corrispondenza nei confini amministrativi 2026, tipicamente per variazioni amministrative. Sono mantenuti con il codice ISTAT e non vengono assegnati a una località inventata:",
            "",
            ", ".join(f"`{code}`" for code in unmatched_codes),
            "",
        ]
    DOC.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not OD_2021.exists():
        raise FileNotFoundError(OD_2021)
    for required in ("routes.txt", "trips.txt", "stop_times.txt", "stops.txt"):
        if not (GTFS / required).exists():
            raise FileNotFoundError(GTFS / required)

    municipalities = download_national_municipalities()
    names = code_name_map(municipalities)
    s8_stops = read_gtfs_s8_stops(municipalities)
    s8_municipalities = set(s8_stops["procom"].astype(str))

    od = pd.read_csv(OD_2021, dtype={"procom_res": str, "procom_lav": str, "pendolari": int})
    od["procom_res"] = od["procom_res"].map(normalize_code)
    od["procom_lav"] = od["procom_lav"].map(normalize_code)
    od["pendolari"] = pd.to_numeric(od["pendolari"], errors="raise").astype(int)
    if (od["pendolari"] <= 0).any():
        raise RuntimeError("2021 OD contains non-positive flows")
    if od.duplicated(["procom_res", "procom_lav"]).any():
        raise RuntimeError("2021 OD is not unique by municipality pair")

    resident, aggregate, corridor, inbound = build_profiles(od, names, s8_municipalities)

    used_codes = set(resident["procom_lav"]) | set(inbound["procom_res"])
    unmatched_codes = sorted(code for code in used_codes if code and code not in names)

    resident_path = OUT_DIR / "od_2021_destinations_by_origin.csv"
    aggregate_path = OUT_DIR / "od_2021_top_destinations_aggregate.csv"
    corridor_path = OUT_DIR / "od_2021_corridor_summary.csv"
    inbound_path = OUT_DIR / "od_2021_inbound_origins_by_destination.csv"
    s8_path = OUT_DIR / "s8_station_municipalities.csv"
    validation_path = OUT_DIR / "od_2021_demand_profile_validation.json"

    resident.to_csv(resident_path, index=False, float_format="%.6f", lineterminator="\n")
    aggregate.to_csv(aggregate_path, index=False, float_format="%.6f", lineterminator="\n")
    corridor.to_csv(corridor_path, index=False, float_format="%.6f", lineterminator="\n")
    inbound.to_csv(inbound_path, index=False, float_format="%.6f", lineterminator="\n")
    s8_stops.to_csv(s8_path, index=False, lineterminator="\n")

    all_core = corridor[corridor["procom"] == "ALL_CORE"].iloc[0]
    expected_resident = 8754
    expected_self = 1315
    if int(all_core["resident_workers"]) != expected_resident:
        raise RuntimeError(
            f"Resident-worker sum changed unexpectedly: {int(all_core['resident_workers'])} != {expected_resident}"
        )
    if int(all_core["self_workers"]) != expected_self:
        raise RuntimeError(f"Self-flow sum changed unexpectedly: {int(all_core['self_workers'])} != {expected_self}")
    if int(all_core["external_workers"]) + int(all_core["core_local_workers"]) != expected_resident:
        raise RuntimeError("Category partition does not sum to resident total")

    write_doc(resident, aggregate, corridor, inbound, s8_stops, unmatched_codes)

    validation = {
        "source_scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
        "od_input": str(OD_2021.relative_to(ROOT)),
        "od_input_sha256": sha256_path(OD_2021),
        "boundary_source": BOUNDARIES_URL,
        "rail_gtfs_routes_sha256": sha256_path(GTFS / "routes.txt"),
        "rail_gtfs_trips_sha256": sha256_path(GTFS / "trips.txt"),
        "rail_gtfs_stop_times_sha256": sha256_path(GTFS / "stop_times.txt"),
        "rail_gtfs_stops_sha256": sha256_path(GTFS / "stops.txt"),
        "core_codes": list(CORE),
        "resident_workers": int(all_core["resident_workers"]),
        "self_workers": int(all_core["self_workers"]),
        "other_core_workers": int(all_core["other_core_workers"]),
        "s8_direct_workers": int(all_core["s8_direct_workers"]),
        "other_external_workers": int(all_core["other_external_workers"]),
        "s8_direct_pct": float(all_core["s8_direct_pct"]),
        "n_s8_gtfs_stop_records": int(len(s8_stops)),
        "n_s8_municipalities": int(len(s8_municipalities)),
        "s8_municipal_codes": sorted(s8_municipalities),
        "unmatched_2021_codes_against_2026_boundaries": unmatched_codes,
        "comparison_2011_status": "DEFERRED_PENDING_NORMALIZATION_AUDIT",
        "classification_note": (
            "S8_DIRECT means destination municipality contains an official S8 GTFS stop; "
            "it is not an observed rail modal share and excludes transfer-reachable destinations."
        ),
        "outputs": {
            str(path.relative_to(ROOT)): sha256_path(path)
            for path in [resident_path, aggregate_path, corridor_path, inbound_path, s8_path, DOC]
        },
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
