#!/usr/bin/env python3
"""Audit and canonicalise the official ISTAT 2011 commuting matrix.

Purpose
-------
Construct a WORK-only, domestic municipal OD matrix for the five Phase 2 core
municipalities that is as close as technically possible to the 2021 work-only
matrix. The parser follows the official 2011 fixed-width record layout, not the
legacy Gate A extraction.

Important methodological boundary
---------------------------------
2011 is a complete census count of people who reported travelling daily from
home to the usual workplace/study place and returning daily. The 2021 matrix is
an estimate from the Permanent Census/register framework and defines work
commuters as employed residents travelling to the usual workplace at least
three days per week; it excludes foreign workplace destinations. Therefore the
resulting 2011->2021 comparison is a descriptive comparison with a documented
series break, not a homogeneous longitudinal estimate.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL_2011 = (
    "https://www.istat.it/storage/cartografia/matrici_pendolarismo/"
    "matrici_pendolarismo_2011.zip"
)
URL_2021 = (
    "https://esploradati.istat.it/databrowser/DWL/PERMPOP/MATPEN/"
    "matrix_pendoLAVORO_2021.zip"
)
MEMBER_2011 = "MATRICE PENDOLARISMO 2011/matrix_pendo2011_10112014.txt"
LEGEND_2011 = "MATRICE PENDOLARISMO 2011/leggimi file matrix_pendo2011_10112014.doc"

CORE_2021 = {
    "097010": "Brivio",
    "097012": "Calco",
    "097058": "Olgiate Molgora",
    "097074": "Santa Maria Hoè",
    "097092": "La Valletta Brianza",
}
CORE_2011_TO_2021 = {
    "097010": "097010",
    "097012": "097012",
    "097058": "097058",
    "097074": "097074",
    "097066": "097092",  # Perego -> La Valletta Brianza
    "097073": "097092",  # Rovagnate -> La Valletta Brianza
}
# Mapping needed inside the five-municipality analysis. Other discontinued
# destinations are retained under their 2011 codes and explicitly flagged;
# they are never silently reassigned.
ADMIN_MAP = {
    # Core merger
    "097066": "097092",  # Perego -> La Valletta Brianza
    "097073": "097092",  # Rovagnate -> La Valletta Brianza
    # Other 2011 destinations actually observed from the five core origins.
    # Map both predecessors of each merger when applicable, even when one has
    # zero observed core flow, so the crosswalk itself is complete.
    "097087": "097091",  # Verderio Inferiore -> Verderio
    "097088": "097091",  # Verderio Superiore -> Verderio
    "097080": "016215",  # Torre de' Busi: Lecco -> Bergamo province recode (2018)
    "012028": "012143",  # Cadrezzate -> Cadrezzate con Osmate
    "012111": "012143",  # Osmate -> Cadrezzate con Osmate
    "013019": "013250",  # Bellagio (old) -> Bellagio (post-fusion)
    "013068": "013250",  # Civenna -> Bellagio
    "015235": "015251",  # Vermezzo -> Vermezzo con Zelo
    "015246": "015251",  # Zelo Surrigone -> Vermezzo con Zelo
    "016039": "016253",  # Brembilla -> Val Brembilla
    "016112": "016253",  # Gerosa -> Val Brembilla
}
S8_CODES_2021 = {
    "097002",  # Airuno
    "108004",  # Arcore
    "097013",  # Calolziocorte
    "108016",  # Carnate
    "097020",  # Cernusco Lombardone
    "097042",  # Lecco
    "015146",  # Milano
    "108033",  # Monza
    "097058",  # Olgiate Molgora
    "097061",  # Osnago
    "015209",  # Sesto San Giovanni
}
KEY_DESTINATIONS = {
    "015146": "Milano",
    "097042": "Lecco",
    "097048": "Merate",
}

OUT_CANON = ROOT / "data/raw/od/matrice_pendolarismo_istat_2011_work_core_canonical.csv"
OUT_AUDIT = ROOT / "outputs/phase2/od_2011_audit.json"
OUT_SUMMARY = ROOT / "outputs/phase2/od_2011_core_summary.csv"
OUT_TREND = ROOT / "outputs/phase2/od_trend_2011_2021.csv"
OUT_DEST = ROOT / "outputs/phase2/od_trend_destinations_2011_2021.csv"
OUT_INTERNAL = ROOT / "outputs/phase2/od_trend_internal_core_2011_2021.csv"
OUT_UNMAPPED = ROOT / "outputs/phase2/od_2011_destination_codes_not_in_2021.csv"


def download(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "tpl-olgiate-phase2-od-audit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        data = response.read()
    if data[:2] != b"PK":
        raise RuntimeError(f"Not a ZIP from {url}: {len(data)} bytes")
    return data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def code6(prov: str, comune: str) -> str:
    return f"{prov.strip().zfill(3)}{comune.strip().zfill(3)}"


def parse_2011(zip_bytes: bytes) -> tuple[list[tuple[str, str, int]], dict]:
    """Parse official S records using the positions documented by ISTAT.

    1-based official positions:
      record 1; residence type 3; province residence 5-7; municipality 9-11;
      sex 14; reason 16; location 18; workplace province 20-22;
      workplace municipality 24-26; foreign state 28-30;
      estimate 39-50; exact Number of individuals 51-60.
    """
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    raw = z.read(MEMBER_2011).decode("latin-1")

    raw_s = 0
    selected_strata = 0
    excluded_study = 0
    excluded_abroad = 0
    excluded_noncore_origin = 0
    by_pair: dict[tuple[str, str], int] = defaultdict(int)
    strata_seen: set[tuple[str, str, str, str, str, str]] = set()
    duplicate_identical_strata = 0
    residence_types: set[str] = set()
    sexes: set[str] = set()
    locations: set[str] = set()

    for line in raw.splitlines():
        if not line.startswith("S"):
            continue
        raw_s += 1
        if len(line) < 60:
            raise RuntimeError(f"Short S record at row {raw_s}: {line!r}")
        residence_type = line[2]
        prov_res = line[4:7]
        com_res = line[8:11]
        sex = line[13]
        reason = line[15]
        location = line[17]
        prov_dest = line[19:22]
        com_dest = line[23:26]
        foreign = line[27:30]
        count_field = line[50:60].strip()

        residence_types.add(residence_type)
        sexes.add(sex)
        locations.add(location)

        origin_2011 = code6(prov_res, com_res)
        if origin_2011 not in CORE_2011_TO_2021:
            excluded_noncore_origin += 1
            continue
        if reason != "2":
            excluded_study += 1
            continue
        if location == "3":
            excluded_abroad += 1
            continue
        if location not in {"1", "2"}:
            raise RuntimeError(f"Unexpected location={location!r} in S record")
        if not count_field.isdigit():
            raise RuntimeError(f"Invalid Number of individuals={count_field!r}")
        value = int(count_field)
        if value <= 0:
            continue

        # For same-municipality records ISTAT still supplies the habitual
        # workplace municipality; use it and assert semantic consistency.
        dest_2011 = code6(prov_dest, com_dest)
        if location == "1" and dest_2011 != origin_2011:
            raise RuntimeError(
                f"2011 semantic mismatch: location=same but {origin_2011}->{dest_2011}"
            )
        if location == "2" and dest_2011 == origin_2011:
            raise RuntimeError(
                f"2011 semantic mismatch: location=other but {origin_2011}->{dest_2011}"
            )
        if foreign.strip() not in {"", "000"}:
            raise RuntimeError("Domestic S record has nonzero foreign-state code")

        # S strata are disjoint by residence type x sex x reason x location x OD.
        stratum = (
            residence_type, origin_2011, sex, reason, location, dest_2011
        )
        if stratum in strata_seen:
            duplicate_identical_strata += 1
            raise RuntimeError(f"Duplicate exact S stratum: {stratum}")
        strata_seen.add(stratum)
        selected_strata += 1

        origin = CORE_2011_TO_2021[origin_2011]
        dest = ADMIN_MAP.get(dest_2011, dest_2011)
        by_pair[(origin, dest)] += value

    rows = [(o, d, by_pair[(o, d)]) for o, d in sorted(by_pair)]
    meta = {
        "source_zip_sha256": sha256(zip_bytes),
        "source_member": MEMBER_2011,
        "official_record_layout_member": LEGEND_2011,
        "raw_S_records": raw_s,
        "selected_work_domestic_core_strata": selected_strata,
        "selected_unique_harmonised_od_pairs": len(rows),
        "excluded_study_after_core_filter": excluded_study,
        "excluded_abroad_after_core_work_filter": excluded_abroad,
        "excluded_noncore_origin_S_records": excluded_noncore_origin,
        "duplicate_exact_S_strata": duplicate_identical_strata,
        "observed_residence_types": sorted(residence_types),
        "observed_sexes": sorted(sexes),
        "observed_locations": sorted(locations),
        "counter_field": "Numero di individui (official columns 51-60)",
        "record_type": "S only",
        "reason_filter": "2 = work",
        "location_filter": "1/2 = domestic, excludes 3 = abroad",
        "administrative_harmonisation": {
            k: v for k, v in ADMIN_MAP.items()
        },
    }
    return rows, meta


def parse_2021(zip_bytes: bytes) -> tuple[list[tuple[str, str, int]], set[str], dict]:
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    members = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith((".txt", ".csv"))]
    primary = max(members, key=lambda i: i.file_size)
    raw = z.read(primary).decode("utf-8-sig")
    sample = raw[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";"
    reader = csv.DictReader(io.StringIO(raw), delimiter=delim)
    if not reader.fieldnames:
        raise RuntimeError("2021 matrix has no header")
    header = {x.strip().upper(): x for x in reader.fieldnames}

    def resolve(*aliases: str) -> str:
        for a in aliases:
            if a in header:
                return header[a]
        raise RuntimeError(f"Missing 2021 field {aliases}; header={reader.fieldnames}")

    oc = resolve("PROCOM_RES", "ITTER107_RES", "COD_RES", "ORIGINE")
    dc = resolve("PROCOM_LAV", "PROCOM_DEST", "ITTER107_DEST", "COD_DEST", "DESTINAZIONE")
    vc = resolve("PENDOLARI", "OBS_VALUE", "VALUE", "STIMA", "NUMERO")
    out: dict[tuple[str, str], int] = defaultdict(int)
    active_codes: set[str] = set()
    national_rows = 0
    national_sum = 0
    for r in reader:
        try:
            o = ''.join(c for c in str(r[oc]) if c.isdigit()).zfill(6)
            d = ''.join(c for c in str(r[dc]) if c.isdigit()).zfill(6)
            v = int(round(float(str(r[vc]).strip().replace(",", "."))))
        except (ValueError, TypeError):
            continue
        if len(o) != 6 or len(d) != 6 or v <= 0:
            continue
        national_rows += 1
        national_sum += v
        active_codes.update((o, d))
        if o in CORE_2021:
            out[(o, d)] += v
    rows = [(o, d, out[(o, d)]) for o, d in sorted(out)]
    return rows, active_codes, {
        "source_zip_sha256": sha256(zip_bytes),
        "source_member": primary.filename,
        "national_positive_od_rows": national_rows,
        "national_commuters_sum": national_sum,
        "core_origin_unique_od_pairs": len(rows),
    }


def write_rows(path: Path, rows: list[tuple[str, str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["procom_res", "procom_lav", "pendolari"])
        w.writerows(rows)


def to_dict(rows: list[tuple[str, str, int]]) -> dict[tuple[str, str], int]:
    return {(o, d): v for o, d, v in rows}


def summary_by_origin(rows: list[tuple[str, str, int]]) -> dict[str, dict[str, int]]:
    out = {c: {"self": 0, "other_core": 0, "s8_external": 0, "other_external": 0, "total": 0} for c in CORE_2021}
    for o, d, v in rows:
        if o not in out:
            continue
        out[o]["total"] += v
        if d == o:
            out[o]["self"] += v
        elif d in CORE_2021:
            out[o]["other_core"] += v
        elif d in S8_CODES_2021:
            out[o]["s8_external"] += v
        else:
            out[o]["other_external"] += v
    return out


def write_summary(rows: list[tuple[str, str, int]]) -> None:
    s = summary_by_origin(rows)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SUMMARY.open("w", newline="", encoding="utf-8") as f:
        fields = ["procom", "comune", "self_workers", "other_core_workers", "s8_external_workers", "other_external_workers", "resident_work_commuters", "self_containment_pct"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for c, name in CORE_2021.items():
            x = s[c]
            w.writerow({
                "procom": c, "comune": name,
                "self_workers": x["self"],
                "other_core_workers": x["other_core"],
                "s8_external_workers": x["s8_external"],
                "other_external_workers": x["other_external"],
                "resident_work_commuters": x["total"],
                "self_containment_pct": f"{100*x['self']/x['total']:.6f}" if x["total"] else "",
            })


def write_trend(r11: list[tuple[str, str, int]], r21: list[tuple[str, str, int]]) -> None:
    s11, s21 = summary_by_origin(r11), summary_by_origin(r21)
    OUT_TREND.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TREND.open("w", newline="", encoding="utf-8") as f:
        fields = ["procom", "comune", "resident_work_2011", "resident_work_2021", "change_abs", "change_pct", "self_2011", "self_2021", "self_containment_2011_pct", "self_containment_2021_pct", "self_containment_change_pp", "other_core_2011", "other_core_2021", "s8_external_2011", "s8_external_2021"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for c, name in CORE_2021.items():
            a,b=s11[c],s21[c]
            p11=100*a["self"]/a["total"] if a["total"] else 0
            p21=100*b["self"]/b["total"] if b["total"] else 0
            w.writerow({
                "procom":c,"comune":name,
                "resident_work_2011":a["total"],"resident_work_2021":b["total"],
                "change_abs":b["total"]-a["total"],
                "change_pct":f"{100*(b['total']/a['total']-1):.6f}" if a["total"] else "",
                "self_2011":a["self"],"self_2021":b["self"],
                "self_containment_2011_pct":f"{p11:.6f}","self_containment_2021_pct":f"{p21:.6f}",
                "self_containment_change_pp":f"{p21-p11:.6f}",
                "other_core_2011":a["other_core"],"other_core_2021":b["other_core"],
                "s8_external_2011":a["s8_external"],"s8_external_2021":b["s8_external"],
            })
        a11=sum(x["total"] for x in s11.values()); a21=sum(x["total"] for x in s21.values())
        self11=sum(x["self"] for x in s11.values()); self21=sum(x["self"] for x in s21.values())
        w.writerow({
            "procom":"TOTAL5","comune":"Totale 5 comuni",
            "resident_work_2011":a11,"resident_work_2021":a21,
            "change_abs":a21-a11,"change_pct":f"{100*(a21/a11-1):.6f}" if a11 else "",
            "self_2011":self11,"self_2021":self21,
            "self_containment_2011_pct":f"{100*self11/a11:.6f}" if a11 else "",
            "self_containment_2021_pct":f"{100*self21/a21:.6f}" if a21 else "",
            "self_containment_change_pp":f"{100*self21/a21-100*self11/a11:.6f}" if a11 and a21 else "",
            "other_core_2011":sum(x["other_core"] for x in s11.values()),
            "other_core_2021":sum(x["other_core"] for x in s21.values()),
            "s8_external_2011":sum(x["s8_external"] for x in s11.values()),
            "s8_external_2021":sum(x["s8_external"] for x in s21.values()),
        })


def write_destination_trends(r11: list[tuple[str, str, int]], r21: list[tuple[str, str, int]]) -> None:
    d11, d21 = to_dict(r11), to_dict(r21)
    OUT_DEST.parent.mkdir(parents=True, exist_ok=True)
    with OUT_DEST.open("w", newline="", encoding="utf-8") as f:
        fields=["origin","origin_name","destination","destination_name","workers_2011","workers_2021","change_abs","change_pct","category"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for o,oname in CORE_2021.items():
            targets=set(KEY_DESTINATIONS)|S8_CODES_2021|set(CORE_2021)
            for d in sorted(targets):
                a=d11.get((o,d),0); b=d21.get((o,d),0)
                if not (a or b): continue
                if d in KEY_DESTINATIONS: dname=KEY_DESTINATIONS[d]
                elif d in CORE_2021: dname=CORE_2021[d]
                else: dname=d
                category=("CORE" if d in CORE_2021 else "S8" if d in S8_CODES_2021 else "KEY_EXTERNAL")
                w.writerow({"origin":o,"origin_name":oname,"destination":d,"destination_name":dname,"workers_2011":a,"workers_2021":b,"change_abs":b-a,"change_pct":f"{100*(b/a-1):.6f}" if a else "","category":category})


def write_internal(r11: list[tuple[str, str, int]], r21: list[tuple[str, str, int]]) -> None:
    d11,d21=to_dict(r11),to_dict(r21)
    OUT_INTERNAL.parent.mkdir(parents=True,exist_ok=True)
    with OUT_INTERNAL.open("w",newline="",encoding="utf-8") as f:
        fields=["origin","origin_name","destination","destination_name","workers_2011","workers_2021","change_abs","change_pct"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for o,on in CORE_2021.items():
            for d,dn in CORE_2021.items():
                a=d11.get((o,d),0);b=d21.get((o,d),0)
                w.writerow({"origin":o,"origin_name":on,"destination":d,"destination_name":dn,"workers_2011":a,"workers_2021":b,"change_abs":b-a,"change_pct":f"{100*(b/a-1):.6f}" if a else ""})


def top_destinations(rows: list[tuple[str,str,int]], n:int=15) -> dict[str,list[dict]]:
    by_o: dict[str,list[tuple[str,int]]]=defaultdict(list)
    for o,d,v in rows: by_o[o].append((d,v))
    return {o:[{"destination":d,"workers":v} for d,v in sorted(vals,key=lambda x:(-x[1],x[0]))[:n]] for o,vals in by_o.items()}


def main() -> int:
    z11=download(URL_2011); z21=download(URL_2021)
    r11,m11=parse_2011(z11); r21,active21,m21=parse_2021(z21)
    if len({(o,d) for o,d,_ in r11}) != len(r11): raise RuntimeError("Duplicate 2011 canonical OD")
    if len({(o,d) for o,d,_ in r21}) != len(r21): raise RuntimeError("Duplicate 2021 canonical OD")
    write_rows(OUT_CANON,r11); write_summary(r11); write_trend(r11,r21); write_destination_trends(r11,r21); write_internal(r11,r21)

    # Do not invent crosswalks for discontinued non-core destinations. Flag them.
    missing=defaultdict(int)
    for o,d,v in r11:
        if d not in active21 and d not in ADMIN_MAP.values(): missing[d]+=v
    with OUT_UNMAPPED.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(["destination_2011_code","workers_from_core_2011"])
        for d,v in sorted(missing.items(),key=lambda x:(-x[1],x[0])):w.writerow([d,v])

    totals11=summary_by_origin(r11); totals21=summary_by_origin(r21)
    audit={
      "verdict":"VALIDATED_WITH_SERIES_BREAK",
      "comparison_scope":"WORK only; domestic destinations only; residents of the five current core municipalities after explicit 2011->2021 core geography harmonisation",
      "2011":m11,"2021":m21,
      "known_legacy_gate_a_errors":[
        "Gate A uses wrong fixed-width offsets: official sex=col14, reason=col16, location=col18, destination province=20-22, municipality=24-26, Number of individuals=51-60.",
        "Gate A legacy extraction reads line[12], line[14], line[16], destination line[18:21]/[22:25] and line[40:50], so its CSV is not a valid OD reconstruction.",
        "Gate A maps Perego/Rovagnate as municipal progressives 067/072; official 2011 codes are 066/073."
      ],
      "comparability":{
        "compatible_dimensions":["resident origin municipality","usual workplace municipality in Italy","work reason"],
        "non_homogeneous_dimensions":[
          "2011 is complete census count; 2021 is Permanent Census/register-based estimate",
          "2011 daily travel-and-return definition; 2021 usual workplace attendance at least three days/week",
          "2021 reference date 31-12-2021 falls in pandemic/smart-working period"
        ],
        "interpretation":"Use absolute/percentage differences as descriptive observed-series differences only. Do not interpret the full change as behavioural or causal change."
      },
      "resident_work_commuters_2011":{c:totals11[c]["total"] for c in CORE_2021},
      "resident_work_commuters_2021":{c:totals21[c]["total"] for c in CORE_2021},
      "top_destinations_2011":top_destinations(r11),
      "top_destinations_2021":top_destinations(r21),
      "unmapped_2011_destination_codes_not_observed_in_2021":len(missing),
      "outputs":[str(p.relative_to(ROOT)) for p in (OUT_CANON,OUT_SUMMARY,OUT_TREND,OUT_DEST,OUT_INTERNAL,OUT_UNMAPPED)]
    }
    OUT_AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
