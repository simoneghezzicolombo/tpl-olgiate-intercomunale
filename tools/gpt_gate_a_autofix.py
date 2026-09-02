#!/usr/bin/env python3
from pathlib import Path

SCRIPT = Path("scripts/audit_01_fetch_real_inputs.py")
TESTS = Path("tests/test_audit_provenance.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


script = SCRIPT.read_text(encoding="utf-8")

script = replace_once(
    script,
    '''OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
OVERPASS_FALLBACKS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
''',
    '''# Public global Overpass instances currently listed by the OpenStreetMap Wiki.
# private.coffee is the successor of the former kumi.systems instance.
OVERPASS_URL = "https://overpass.private.coffee/api/interpreter"
OVERPASS_FALLBACKS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
''',
    "Overpass endpoint block",
)

script = replace_once(
    script,
    '''            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                timeout=timeout + 30,
            )
''',
    '''            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                # Fail over quickly when a public mirror blocks cloud ranges.
                timeout=(10, min(timeout, 45)),
            )
''',
    "Overpass XML request timeout",
)

script = replace_once(
    script,
    '''            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                timeout=timeout,
            )
''',
    '''            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                timeout=(10, min(timeout, 45)),
            )
''',
    "Overpass JSON request timeout",
)

old_sfr = '''    def prepare(
        df: pd.DataFrame,
        day_col: str,
        source_label: str,
        min_year: int,
        max_year: int,
    ) -> pd.DataFrame:
        required = {"Campagna", "Stazione", "Saliti24H", "Anno", day_col}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"SFR schema changed; missing {sorted(missing)}")
        d = df.copy()
        d["Anno"] = pd.to_numeric(d["Anno"], errors="coerce")
        d["Saliti24H"] = pd.to_numeric(d["Saliti24H"], errors="coerce")
        d["_station_key"] = d["Stazione"].map(_norm_station)
        d["Stazione_std"] = d["_station_key"].map(S8_DISPLAY)
        d = d[
            d["Stazione_std"].notna()
            & d["Anno"].between(min_year, max_year)
            & d["Campagna"].map(_month_is_november)
            & d[day_col].map(_day_is_weekday)
        ].copy()
        d["Fonte_periodo"] = source_label
        return d[["Anno", "Stazione_std", "Saliti24H", "Fonte_periodo"]]

    hist_s8 = prepare(
        hist,
        "tipo_giorno",
        "Flussi Stazioni Ferroviarie (2015-2023; m2u2-frtq)",
        2015,
        2023,
    )
    recent_s8 = prepare(
        recent,
        "Tipo giorno",
        "Frequentazione stazioni SFR (2024-2025; ut63-s688)",
        2024,
        2025,
    )
'''

new_sfr = '''    def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Map Socrata API field names and display labels to one stable schema."""
        aliases = {
            "campagna": "Campagna",
            "stazione": "Stazione",
            "saliti24h": "Saliti24H",
            "anno": "Anno",
            "tipogiorno": "TipoGiorno",
        }
        rename = {}
        for col in df.columns:
            key = re.sub(r"[^a-z0-9]", "", str(col).lower())
            if key in aliases:
                rename[col] = aliases[key]
        return df.rename(columns=rename)

    def prepare(
        df: pd.DataFrame,
        source_label: str,
        min_year: int,
        max_year: int,
        *,
        filter_weekday: bool,
    ) -> pd.DataFrame:
        d = canonicalize_columns(df.copy())
        required = {"Campagna", "Stazione", "Saliti24H", "Anno"}
        if filter_weekday:
            required.add("TipoGiorno")
        missing = required - set(d.columns)
        if missing:
            raise ValueError(
                f"SFR schema changed; missing {sorted(missing)}; "
                f"available={list(d.columns)}"
            )

        d["Anno"] = pd.to_numeric(d["Anno"], errors="coerce")
        d["Saliti24H"] = pd.to_numeric(d["Saliti24H"], errors="coerce")
        d["_station_key"] = d["Stazione"].map(_norm_station)
        d["Stazione_std"] = d["_station_key"].map(S8_DISPLAY)

        mask = (
            d["Stazione_std"].notna()
            & d["Anno"].between(min_year, max_year)
            & d["Campagna"].map(_month_is_november)
        )
        # Regione Lombardia documents 2015-2023 as weekday-mean only.
        # From 2024 onward the dataset distinguishes weekday/Saturday/holiday.
        if filter_weekday:
            mask &= d["TipoGiorno"].map(_day_is_weekday)

        d = d[mask].copy()
        d["Fonte_periodo"] = source_label
        return d[["Anno", "Stazione_std", "Saliti24H", "Fonte_periodo"]]

    hist_s8 = prepare(
        hist,
        "Flussi Stazioni Ferroviarie (2015-2023; m2u2-frtq)",
        2015,
        2023,
        filter_weekday=False,
    )
    recent_s8 = prepare(
        recent,
        "Frequentazione stazioni SFR (2024-2025; ut63-s688)",
        2024,
        2025,
        filter_weekday=True,
    )
'''
script = replace_once(script, old_sfr, new_sfr, "SFR preparation block")

script = replace_once(
    script,
    '''            f"(2024-2025, {SFR_RECENT_CSV}). Filter November weekday records, "
            "harmonize station names and Saliti24H, then compute Indice_2019_100. "
''',
    '''            f"(2024-2025, {SFR_RECENT_CSV}). Filter November campaigns; "
            "2015-2023 is already weekday-mean in the official source, while from "
            "2024 TipoGiorno is filtered to weekday. Harmonize station names and "
            "Saliti24H, then compute Indice_2019_100. "
''',
    "SFR manifest methodology wording",
)

SCRIPT.write_text(script, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
old_test = '''    hist = pd.DataFrame({
        "Campagna": [f"C_nov {year}" for year in range(2015, 2024)],
        "Stazione": ["OLGIATE-CALCO-BRIVIO"] * 9,
        "Saliti24H": [1000 + 50 * (year - 2015) for year in range(2015, 2024)],
        "Anno": list(range(2015, 2024)),
        "tipo_giorno": ["Feriale"] * 9,
    })
    recent = pd.DataFrame({
        "Campagna": ["c2024Novembre", "c2025Novembre"],
        "Stazione": ["OLGIATE-CALCO-BRIVIO"] * 2,
        "Saliti24H": [1800, 2000],
        "Anno": [2024, 2025],
        "Tipo giorno": ["Feriale", "Feriale"],
    })
'''
new_test = '''    # Match Socrata resource API field naming: lower-case/underscore identifiers.
    # Historical 2015-2023 is documented by Regione Lombardia as weekday-mean only,
    # so the rebuild must not require a day-type column for that source.
    hist = pd.DataFrame({
        "campagna": [f"C_nov {year}" for year in range(2015, 2024)],
        "stazione": ["OLGIATE-CALCO-BRIVIO"] * 9,
        "saliti24h": [1000 + 50 * (year - 2015) for year in range(2015, 2024)],
        "anno": list(range(2015, 2024)),
    })
    recent = pd.DataFrame({
        "campagna": ["c2024Novembre", "c2025Novembre", "c2025Novembre"],
        "stazione": ["OLGIATE-CALCO-BRIVIO"] * 3,
        "saliti24h": [1800, 2000, 9999],
        "anno": [2024, 2025, 2025],
        "tipo_giorno": ["Feriale", "Feriale", "Sabato"],
    })
'''
tests = replace_once(tests, old_test, new_test, "SFR deterministic test fixture")

# Prove that the 2025 Saturday row is excluded by the post-2024 weekday filter.
tests = replace_once(
    tests,
    '''    assert olg.loc[olg["Anno"] == 2019, "Indice_2019_100"].iloc[0] == pytest.approx(100.0)
''',
    '''    assert olg.loc[olg["Anno"] == 2019, "Indice_2019_100"].iloc[0] == pytest.approx(100.0)
    assert olg.loc[olg["Anno"] == 2025, "Saliti24H"].iloc[0] == pytest.approx(2000.0)
''',
    "SFR weekday assertion",
)

TESTS.write_text(tests, encoding="utf-8")
print("Applied Gate A SFR/Overpass patch successfully.")
