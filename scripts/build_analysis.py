#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LinearRegression, RidgeCV, ElasticNetCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy.stats import norm

MIGRATION_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97"
POPULATION_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy"
INCOME_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/HE/HE0110/HE0110A/SamForvInk2"
INEQUALITY_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/HE/HE0110/HE0110I/Tab4InkDesoRegso"
TURNOUT_SOURCES = {
    2018: {
        "municipality": {
            "page": "https://historik.val.se/val/val2018/statistik/index.html",
            "link_text": "2018_R_per_kommun.xlsx",
        },
        "district": {
            "page": "https://historik.val.se/val/val2018/statistik/index.html",
            "link_text": "2018_R_per_valdistrikt.xlsx",
        },
    },
    2022: {
        "combined": {
            "page": "https://www.val.se/valresultat-och-statistik/statistik-och-data/radata-fran-val-2002-2022",
            "link_text": "Röster per distrikt, slutligt antal röster, inklusive totalt valdeltagande, riksdagsvalet 2022",
        },
    },
    2026: {
        "combined": {
            "page": "https://www.val.se/valresultat-och-statistik/statistik-och-data/radata-val-2026",
            "link_text": "Röster per distrikt i riksdagsvalet 2026, slutlig rösträkning",
        },
    },
}

# Secondary public references supplied for independent sanity checks.  These are
# intentionally non-blocking: Valmyndigheten remains the primary source because
# its machine-readable workbooks are more stable than presentation HTML.
SVT_TURNOUT_REFERENCE_URLS = [
    "https://valresultat.svt.se/2018/10000.html",
    "https://valresultat.svt.se/2026/riksdagsval-0764-alvesta.html",
]

LOOKAHEAD_ONLY_FEATURES = {
    "lag1_valdeltagande_pct",
    "lag1_valdeltagande_gap_pp",
}
HOUSING_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
COMPLETED_HOUSING_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0101/BO0101A/LghReHtypUfAr"
LEISURE_HOUSE_URL_CANDIDATES = [
    # Exact branch from SCB PxWeb: START__BO__BO0104__BO0104H/BO0104T08
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104H/BO0104T08",
    # Fallback variants retained only for diagnosis.
    # SCB's PxWeb UI calls the table BO0104T08 while metadata may expose another matrix id.
    # Try stable API variants explicitly and fail during preflight, not after the long build.
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/BO/BO0104/BO0104AI",
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104X/BO0104AI",
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/BO/BO0104/BO0104T08",
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104T08",
    "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104X/BO0104T08",
]
_LEISURE_HOUSE_RESOLVED_URL = None
BRA_ANNUAL_RAW = "https://raw.githubusercontent.com/Lulea-statistik/BR-brottsstatistik/main/data/annual_all/year={year}.parquet"
LABOR_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210A/ArbStatusAr"
EDUCATION_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/UF/UF0506/UF0506B/Utbildning"
STUDENT_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AA/AA0003/AA0003H/IntGr8Kom1N"
INDUSTRY_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210F/ArRegUtb"
FA15_XLSX_URL = "https://tillvaxtverket.se/download/18.8fc3d8b1855c7f9043216/1672314363587/FA-regioner%202015%20%C3%A5r%20indelning%20%281%29.xlsx"
OUT = Path("docs/data")
OUT.mkdir(parents=True, exist_ok=True)

START_YEAR = 2002
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))
# Auxiliary explanatory variables only need to cover the longest analysis
# window plus one lag year.
AUX_YEARS = list(range(max(2013, END_YEAR - 6), END_YEAR + 1))

session = requests.Session()
session.headers.update({"User-Agent": "Samband-inflyttning/1.0"})


def metadata(url: str) -> dict:
    last_error = None
    for attempt in range(1, 5):
        try:
            r = session.get(url, timeout=60)
            if r.ok:
                return r.json()
            if r.status_code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"SCB metadata failed {r.status_code} for {url}: {r.text[:500]}"
                )
            last_error = RuntimeError(
                f"SCB metadata transient HTTP {r.status_code} for {url}: {r.text[:300]}"
            )
        except requests.RequestException as exc:
            last_error = exc

        if attempt < 4:
            wait = 2 * attempt
            print(f"Metadata retry {attempt}/4 for {url} after {last_error}; waiting {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"SCB metadata failed after 4 attempts for {url}: {last_error}")


def resolve_leisure_house_url() -> tuple[str, dict]:
    global _LEISURE_HOUSE_RESOLVED_URL
    if _LEISURE_HOUSE_RESOLVED_URL is not None:
        return _LEISURE_HOUSE_RESOLVED_URL, metadata(_LEISURE_HOUSE_RESOLVED_URL)

    errors = []
    for url in LEISURE_HOUSE_URL_CANDIDATES:
        try:
            meta = metadata(url)
            if not meta.get("variables"):
                raise RuntimeError("metadata contains no variables")
            _LEISURE_HOUSE_RESOLVED_URL = url
            print(f"Resolved leisure-house API: {url}")
            return url, meta
        except Exception as exc:
            errors.append(f"{url} -> {exc}")
            print(f"Leisure-house candidate failed: {url} -> {exc}")

    raise RuntimeError(
        "No working SCB leisure-house v1 endpoint found. Tried:\n- "
        + "\n- ".join(errors)
    )


def preflight_sources() -> None:
    """
    Fail fast before the expensive panel build if an external source URL,
    table id or schema endpoint has changed.
    """
    scb_sources = {
        "migration": MIGRATION_URL,
        "population": POPULATION_URL,
        "income": INCOME_URL,
        "socioeconomic_gap": INEQUALITY_URL,
        "housing": HOUSING_URL,
        "completed_housing": COMPLETED_HOUSING_URL,
        "labor": LABOR_URL,
        "education": EDUCATION_URL,
        "students": STUDENT_URL,
        "industry": INDUSTRY_URL,
    }

    print("Preflight: validating SCB metadata endpoints...")
    failures = []
    for name, url in scb_sources.items():
        started = time.time()
        try:
            meta = metadata(url)
            variables = meta.get("variables", [])
            if not variables:
                raise RuntimeError("metadata contains no variables")
            elapsed = time.time() - started
            print(f"Preflight OK {name}: {len(variables)} variables ({elapsed:.1f}s)")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"Preflight FAILED {name}: {exc}")

    try:
        url, meta = resolve_leisure_house_url()
        print(f"Preflight OK leisure_houses: {len(meta.get('variables', []))} variables via {url}")
    except Exception as exc:
        failures.append(f"leisure_houses: {exc}")
        print(f"Preflight FAILED leisure_houses: {exc}")

    # Lightweight checks of the non-SCB sources used in the build.
    try:
        r = session.get(BRA_ANNUAL_RAW.format(year=END_YEAR), timeout=30, stream=True)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code}")
        print(f"Preflight OK BRÅ annual parquet {END_YEAR}")
        r.close()
    except Exception as exc:
        failures.append(f"BRÅ annual parquet: {exc}")
        print(f"Preflight FAILED BRÅ annual parquet: {exc}")

    try:
        r = session.get(FA15_XLSX_URL, timeout=30, stream=True)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code}")
        print("Preflight OK FA15 workbook")
        r.close()
    except Exception as exc:
        failures.append(f"FA15 workbook: {exc}")
        print(f"Preflight FAILED FA15 workbook: {exc}")

    for election_year, sources in TURNOUT_SOURCES.items():
        for level, source_spec in sources.items():
            try:
                source_url = _resolve_external_file(source_spec)
                r = session.get(source_url, timeout=30, stream=True)
                if not r.ok:
                    raise RuntimeError(f"HTTP {r.status_code}")
                print(f"Preflight OK riksdags-turnout {election_year} {level}")
                r.close()
            except Exception as exc:
                failures.append(f"riksdags-turnout {election_year} {level}: {exc}")
                print(f"Preflight FAILED riksdags-turnout {election_year} {level}: {exc}")

    # SVT is a useful independent reference/fallback, but it must never make the
    # build fail when Valmyndigheten's official source is healthy.
    for source_url in SVT_TURNOUT_REFERENCE_URLS:
        try:
            r = session.get(source_url, timeout=20, stream=True)
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code}")
            print(f"Preflight OK optional SVT turnout reference: {source_url}")
            r.close()
        except Exception as exc:
            print(f"Preflight WARNING optional SVT turnout reference unavailable: {source_url} -> {exc}")

    if failures:
        raise RuntimeError(
            "External-source preflight failed before the full build:\n- "
            + "\n- ".join(failures)
        )
    print("Preflight complete: all external sources reachable.")


def find_var(meta: dict, *needles: str) -> dict:
    needles = tuple(n.lower() for n in needles)
    for v in meta["variables"]:
        hay = f'{v.get("code","")} {v.get("text","")}'.lower()
        if any(n in hay for n in needles):
            return v
    raise KeyError(f"Variable not found: {needles}")


def code_for_text(var: dict, wanted: str) -> str:
    wanted_l = wanted.lower()
    for code, text in zip(var["values"], var.get("valueTexts", var["values"])):
        if text.lower() == wanted_l:
            return code
    for code, text in zip(var["values"], var.get("valueTexts", var["values"])):
        if wanted_l in text.lower():
            return code
    raise KeyError(f"Value {wanted!r} not found in {var.get('text')}")


def aggregate_codes(var: dict) -> list[str]:
    """Use one total category when present; otherwise use all component categories."""
    pairs = list(zip(var["values"], var.get("valueTexts", var["values"])))
    preferred = {"totalt", "total", "samtliga", "alla", "båda könen", "bada konen"}
    for code, text in pairs:
        if str(text).strip().lower() in preferred:
            return [code]
    for code, text in pairs:
        t = str(text).strip().lower()
        if "totalt" in t or "samtliga" in t or "båda könen" in t or "bada konen" in t:
            return [code]
    return [code for code, _ in pairs]


def code_for_all_text(var: dict, *needles: str) -> str:
    needles_l = [n.lower() for n in needles]
    for code, text in zip(var["values"], var.get("valueTexts", var["values"])):
        t = str(text).lower()
        if all(n in t for n in needles_l):
            return code
    raise KeyError(f"Value containing {needles!r} not found in {var.get('text')}")


def exact_or_contains_code(var: dict, wanted: str) -> str:
    wanted_l = wanted.lower().strip()
    for code, text in zip(var["values"], var.get("valueTexts", var["values"])):
        if str(text).lower().strip() == wanted_l:
            return code
    for code, text in zip(var["values"], var.get("valueTexts", var["values"])):
        if wanted_l in str(text).lower():
            return code
    raise KeyError(f"Value {wanted!r} not found in {var.get('text')}")


def require_total_code(var: dict) -> str:
    """Return a genuine total category; do not aggregate percentage strata."""
    pairs = list(zip(var["values"], var.get("valueTexts", var["values"])))
    preferred = {"totalt", "total", "samtliga", "alla", "samtliga utbildningar"}
    for code, text in pairs:
        if str(text).strip().lower() in preferred:
            return code
    for code, text in pairs:
        t = str(text).strip().lower()
        if "totalt" in t or "samtliga" in t:
            return code
    raise KeyError(f"No total category found in {var.get('text')}: {[t for _, t in pairs[:30]]}")


def municipality_codes(region_var: dict) -> list[str]:
    """
    Return the table's own municipality selector codes.
    SCB uses several region-code conventions across tables: plain 0180,
    prefixed variants such as K0180, or labels beginning with the four-digit
    municipality code. Keep the original selector value that the table expects.
    """
    values = list(region_var["values"])
    texts = list(region_var.get("valueTexts", values))
    out = []
    for value, text in zip(values, texts):
        v = str(value).strip()
        t = str(text).strip()

        is_municipality = bool(re.fullmatch(r"\d{4}", v))
        if not is_municipality:
            is_municipality = bool(re.fullmatch(r"[^0-9]*\d{4}", v))
        if not is_municipality:
            is_municipality = bool(re.match(r"^\d{4}(?:\s|\b)", t))

        if is_municipality:
            out.append(v)

    if not out:
        raise ValueError(
            f"No municipality region codes identified in {region_var.get('text')}. "
            f"Sample values={values[:10]}, sample labels={texts[:10]}"
        )
    return out


def px_csv(url: str, selections: dict[str, list[str]]) -> pd.DataFrame:
    query = []
    for code, values in selections.items():
        query.append({"code": code, "selection": {"filter": "item", "values": values}})
    payload = {"query": query, "response": {"format": "csv"}}

    last_error = None
    for attempt in range(1, 5):
        try:
            r = session.post(url, json=payload, timeout=180)
            if r.ok:
                return pd.read_csv(io.StringIO(r.text), sep=None, engine="python")

            if r.status_code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"SCB query failed {r.status_code} for {url}: {r.text[:1000]} "
                    f"| selections={json.dumps(selections, ensure_ascii=False)}"
                )
            last_error = RuntimeError(
                f"Transient SCB HTTP {r.status_code} for {url}: {r.text[:500]}"
            )
        except requests.RequestException as exc:
            last_error = exc

        if attempt < 4:
            wait_seconds = 2 * attempt
            print(f"SCB transient error, retry {attempt}/4 after {wait_seconds}s: {last_error}")
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"SCB query failed after 4 attempts for {url}: {last_error} "
        f"| selections={json.dumps(selections, ensure_ascii=False)}"
    )


def normalize_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace({"..": np.nan, ".": np.nan, "nan": np.nan}),
        errors="coerce",
    )


def age_numeric(label: str) -> float:
    x = str(label).lower().replace("år", "").strip()
    if "tot" in x:
        return np.nan
    if "+" in x:
        try:
            return float(x.replace("+", "").strip())
        except ValueError:
            return np.nan
    if "–" in x or "-" in x:
        sep = "–" if "–" in x else "-"
        try:
            a, b = [float(z.strip()) for z in x.split(sep, 1)]
            return (a + b) / 2
        except ValueError:
            return np.nan
    try:
        return float(x)
    except ValueError:
        return np.nan


def get_migration() -> pd.DataFrame:
    meta = metadata(MIGRATION_URL)
    region = find_var(meta, "region")
    age = find_var(meta, "ålder", "alder")
    sex = find_var(meta, "kön", "kon")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    inflow_code = code_for_text(content, "Inflyttningar")
    outflow_code = code_for_text(content, "Utflyttningar")
    sex_codes = aggregate_codes(sex)
    rows = []

    # One year at a time stays safely below PxWeb cell limits.
    # SCB encodes the selected year in the value-column header
    # (for example "Inflyttningar 2002"), so normalize each yearly
    # response before concatenating.
    for year in YEARS:
        df = px_csv(MIGRATION_URL, {
            region["code"]: munis,
            age["code"]: list(age["values"]),
            sex["code"]: sex_codes,
            content["code"]: [inflow_code, outflow_code],
            time["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        value_candidates = [c for c in df.columns if c not in set(dims.values())]
        inflow_col = next(
            (c for c in value_candidates if "inflytt" in str(c).lower()),
            None,
        )
        outflow_col = next(
            (c for c in value_candidates if "utflytt" in str(c).lower()),
            None,
        )
        if inflow_col is None or outflow_col is None:
            raise ValueError(
                f"Could not identify inflow/outflow columns for {year}: "
                f"{value_candidates}"
            )
        df = df.rename(columns={
            inflow_col: "value",
            outflow_col: "utflyttning_value",
        })
        df["year"] = year
        rows.append(df)
        print(f"Migration in/out {year}: {len(df):,} rows")
    return pd.concat(rows, ignore_index=True)


def get_population() -> pd.DataFrame:
    meta = metadata(POPULATION_URL)
    region = find_var(meta, "region")
    age = find_var(meta, "ålder", "alder")
    sex = find_var(meta, "kön", "kon")
    civil = find_var(meta, "civilstånd", "civilstand")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    pop_code = code_for_text(content, "Folkmängd")
    sex_codes = aggregate_codes(sex)
    civil_codes = aggregate_codes(civil)
    age_codes = []
    for code, text in zip(age["values"], age.get("valueTexts", age["values"])):
        a = age_numeric(text)
        if (
            (np.isfinite(a) and (18 <= a <= 49 or 63 <= a <= 79))
            or "tot" in str(text).lower()
        ):
            age_codes.append(code)

    rows = []
    for year in YEARS:
        df = px_csv(POPULATION_URL, {
            region["code"]: munis,
            age["code"]: age_codes,
            sex["code"]: sex_codes,
            civil["code"]: civil_codes,
            content["code"]: [pop_code],
            time["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        value_candidates = [c for c in df.columns if c not in set(dims.values())]
        if len(value_candidates) != 1:
            raise ValueError(f"Expected one population value column for {year}, got {value_candidates}")
        df = df.rename(columns={value_candidates[0]: "value"})
        df["year"] = year
        rows.append(df)
        print(f"Population {year}: {len(df):,} rows")
    return pd.concat(rows, ignore_index=True)



def get_income() -> pd.DataFrame:
    """Mean earned income (tkr) for ages 20-64, aggregated correctly across sex."""
    meta = metadata(INCOME_URL)
    region = find_var(meta, "region")
    age = find_var(meta, "ålder", "alder")
    sex = find_var(meta, "kön", "kon")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    age_code = code_for_all_text(age, "20", "64")
    sex_codes = aggregate_codes(sex)
    total_sum_code = code_for_all_text(content, "totalsumma")
    count_code = code_for_all_text(content, "antal", "person")

    rows = []
    for year in AUX_YEARS:
        df = px_csv(INCOME_URL, {
            region["code"]: munis,
            age["code"]: [age_code],
            sex["code"]: sex_codes,
            content["code"]: [total_sum_code, count_code],
            time["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        sum_col = next((c for c in value_cols if "totalsumma" in str(c).lower()), None)
        count_col = next((c for c in value_cols if "antal" in str(c).lower() and "person" in str(c).lower()), None)
        if not sum_col or not count_col:
            raise ValueError(f"Could not identify income columns for {year}: {list(df.columns)}")
        df["sum_mnkr"] = normalize_number(df[sum_col])
        df["persons"] = normalize_number(df[count_col])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(lambda x: pd.Series(split_region(x)))
        agg = df.groupby(["kommun_kod", "kommun", "year"], as_index=False).agg(
            sum_mnkr=("sum_mnkr", "sum"),
            persons=("persons", "sum"),
        )
        agg["inkomst_tkr"] = 1000 * agg["sum_mnkr"] / agg["persons"].replace(0, np.nan)
        rows.append(agg[["kommun_kod", "kommun", "year", "inkomst_tkr"]])
        print(f"Income {year}: {len(agg):,} municipalities")
    return pd.concat(rows, ignore_index=True)



def _norm_header(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _percent_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _code_digits(value: object) -> str:
    text = str(value or "").strip()
    # Excel often turns codes such as 0114 into numeric 114.0.
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        text = text.split(".", 1)[0]
    return re.sub(r"\D", "", text)


def _municipality_code(value: object, *, from_district: bool = False) -> object:
    digits = _code_digits(value)
    if not digits:
        return np.nan
    if from_district:
        # Valmyndigheten has used both 6-digit and longer polling-district
        # codes across election files. The municipality is always the first
        # four digits after restoring a possible lost leading zero.
        if len(digits) <= 6:
            digits = digits.zfill(6)
        else:
            digits = digits.zfill(8)
        return digits[:4]
    if len(digits) <= 4:
        return digits.zfill(4)
    # Defensive fallback when a district-like code ends up in this column.
    if len(digits) <= 6:
        digits = digits.zfill(6)
    else:
        digits = digits.zfill(8)
    return digits[:4]


def _district_code(value: object) -> object:
    digits = _code_digits(value)
    if not digits:
        return np.nan
    # Preserve the historical 6-digit coding used in older election files;
    # only pad longer modern variants to eight digits.
    return digits.zfill(6 if len(digits) <= 6 else 8)



class _LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._parts).strip()))
            self._href = None
            self._parts = []


def _resolve_external_file(source: object) -> str:
    """Resolve a direct file URL or an official-page link by visible link text."""
    if isinstance(source, str):
        return source
    if not isinstance(source, dict):
        raise TypeError(f"Unsupported source specification: {source!r}")

    direct = source.get("url")
    if direct:
        return str(direct)

    page = source.get("page")
    needle = str(source.get("link_text") or "").strip()
    if not page or not needle:
        raise ValueError(f"Source specification lacks page/link_text: {source!r}")

    r = session.get(str(page), timeout=60)
    r.raise_for_status()
    parser = _LinkCollector()
    parser.feed(r.text)

    needle_norm = _norm_header(needle)
    candidates = []
    for href, text in parser.links:
        text_norm = _norm_header(text)
        href_name = href.rsplit("/", 1)[-1]
        href_norm = _norm_header(href_name)
        if needle_norm in text_norm or needle_norm in href_norm:
            candidates.append(urljoin(str(page), href))

    if not candidates:
        raise RuntimeError(
            f"Could not resolve download link containing {needle!r} from {page}"
        )
    resolved = candidates[0]
    print(f"Resolved turnout source: {needle} -> {resolved}")
    return resolved


def _excel_bytes(url: str) -> bytes:
    last_error = None
    for attempt in range(1, 4):
        try:
            r = session.get(url, timeout=180)
            if r.ok and len(r.content) > 1000:
                return r.content
            last_error = RuntimeError(f"HTTP {r.status_code}, {len(r.content)} bytes")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download Excel source {url}: {last_error}")


def _detected_excel_sheet(content: bytes, sheet_name: str) -> pd.DataFrame:
    probe = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=None, nrows=30)
    best_row = 0
    best_score = -1
    for idx, row in probe.iterrows():
        vals = [_norm_header(x) for x in row.tolist()]
        score = sum(
            4 if "valdeltag" in v else
            2 if ("kommun" in v or "valdistrikt" in v) else
            1 if ("rostberattig" in v or "kod" in v) else 0
            for v in vals if v
        )
        if score > best_score:
            best_score = score
            best_row = int(idx)
    return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=best_row)


def _debug_turnout_workbook(content: bytes, election_year: int) -> None:
    """Print compact workbook schema samples when automatic parsing fails."""
    try:
        xl = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:
        print(f"Turnout debug {election_year}: could not open workbook: {exc}")
        return

    print(f"Turnout debug {election_year}: sheets={xl.sheet_names}")
    for sheet in xl.sheet_names[:12]:
        try:
            raw = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None, nrows=18)
        except Exception as exc:
            print(f"Turnout debug {election_year} sheet {sheet!r}: read failed: {exc}")
            continue

        print(
            f"Turnout debug {election_year} sheet {sheet!r}: "
            f"shape_sample={raw.shape}"
        )
        for idx, row in raw.iterrows():
            vals = []
            for val in row.tolist()[:16]:
                text = str(val).strip()
                if text and text.lower() != "nan":
                    vals.append(text[:80])
                else:
                    vals.append("")
            if any(vals):
                print(f"  row {idx}: {vals}")


def _turnout_rows_from_workbook(
    content: bytes,
    *,
    level_hint: str | None = None,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    """
    Parse Valmyndigheten workbooks across old/new layouts.

    Some workbooks name the turnout column explicitly "Valdeltagande", while
    newer layouts can put turnout on a sheet named Valdeltagande and call the
    numeric column simply Andel/Procent. Geography can likewise be stored in
    dedicated Kommun-/Valdistriktskod columns or a generic Områdeskod column.
    """
    xl = pd.ExcelFile(io.BytesIO(content))
    municipality_frames = []
    district_frames = []

    for sheet in xl.sheet_names:
        try:
            df = _detected_excel_sheet(content, sheet)
        except Exception as exc:
            print(f"Turnout sheet skipped {sheet!r}: {exc}")
            continue
        if df.empty:
            continue

        cols = {c: _norm_header(c) for c in df.columns}
        sheet_norm = _norm_header(sheet)

        turnout_cols = [
            c for c, n in cols.items()
            if "valdeltag" in n and ("tot" in n or "procent" in n or "andel" in n or "%" in str(c))
        ]
        if not turnout_cols:
            turnout_cols = [c for c, n in cols.items() if "valdeltag" in n]
        if not turnout_cols and "valdeltag" in sheet_norm:
            turnout_cols = [
                c for c, n in cols.items()
                if ("andel" in n or "procent" in n or "%" in str(c))
                and "parti" not in n
            ]

        eligible_col = next(
            (c for c, n in cols.items() if "rostberattig" in n and "antal" in n),
            None,
        )
        if eligible_col is None:
            eligible_col = next((c for c, n in cols.items() if "rostberattig" in n), None)

        voted_col = next(
            (
                c for c, n in cols.items()
                if ("rostande" in n or "avgivnaroster" in n or "avgivnarost" in n)
                and "andel" not in n and "procent" not in n
            ),
            None,
        )

        # If no explicit turnout column exists, derive turnout from voters /
        # eligible voters when those counts are available.
        turnout_col = turnout_cols[0] if turnout_cols else None
        if turnout_col is None and not (eligible_col is not None and voted_col is not None):
            continue

        kommun_code_col = next(
            (c for c, n in cols.items() if "kommunkod" in n),
            None,
        )
        county_code_col = next(
            (c for c, n in cols.items() if "lanskod" in n or n == "lan"),
            None,
        )
        district_code_col = next(
            (c for c, n in cols.items() if ("valdistrikt" in n and "kod" in n) or "valdistriktskod" in n),
            None,
        )
        generic_code_col = next(
            (
                c for c, n in cols.items()
                if n in {"kod", "omradeskod", "omradekod", "valomradeskod"}
                or ("omrade" in n and n.endswith("kod"))
            ),
            None,
        )
        kommun_name_col = next(
            (c for c, n in cols.items() if "kommunnamn" in n or n in {"kommun", "kommunnamn"}),
            None,
        )

        out = pd.DataFrame(index=df.index)
        if turnout_col is not None:
            out["turnout"] = _percent_number(df[turnout_col])
            finite_turnout = out["turnout"].dropna()
            if not finite_turnout.empty and finite_turnout.median() <= 1.5:
                out["turnout"] = 100 * out["turnout"]
        else:
            eligible = normalize_number(df[eligible_col])
            voted = normalize_number(df[voted_col])
            out["turnout"] = 100 * voted / eligible.replace(0, np.nan)

        if eligible_col is not None:
            out["rostberattigade"] = normalize_number(df[eligible_col])
        else:
            out["rostberattigade"] = np.nan

        if kommun_name_col is not None:
            out["kommun"] = df[kommun_name_col].astype(str).str.strip()
        else:
            out["kommun"] = np.nan

        # Dedicated geography columns. Use pandas' string dtype from the
        # start; pandas 3.x no longer permits silently assigning strings into
        # a float column that was initialized with np.nan.
        if kommun_code_col is not None:
            raw_kommun = df[kommun_code_col].map(_code_digits).astype("string")
            # Valmyndigheten 2018 stores LÄNSKOD and the two-digit municipal
            # suffix in separate columns. Reconstruct the official 4-digit
            # municipality code (e.g. 01 + 14 = 0114).
            if county_code_col is not None:
                raw_county = df[county_code_col].map(_code_digits).astype("string").str.zfill(2)
                short_suffix = raw_kommun.str.len().le(2)
                combined_code = raw_county + raw_kommun.str.zfill(2)
                parsed_code = raw_kommun.map(_municipality_code).astype("string")
                out["kommun_kod"] = parsed_code.where(~short_suffix, combined_code)
            else:
                out["kommun_kod"] = raw_kommun.map(_municipality_code).astype("string")
        else:
            out["kommun_kod"] = pd.Series(pd.NA, index=df.index, dtype="string")

        if district_code_col is not None:
            out["valdistrikt_kod"] = df[district_code_col].map(_district_code).astype("string")
            derived_muni = df[district_code_col].map(
                lambda x: _municipality_code(x, from_district=True)
            ).astype("string")
            # Prefer an explicit/reconstructed municipality code from the
            # workbook columns. Historical polling-district codes are not
            # guaranteed to embed the municipality code in the same positions.
            missing_muni = out["kommun_kod"].isna()
            out.loc[missing_muni, "kommun_kod"] = derived_muni.loc[missing_muni]
        else:
            out["valdistrikt_kod"] = pd.Series(pd.NA, index=df.index, dtype="string")

        # Generic area-code layouts (used by some 2022/2026 exports).
        if generic_code_col is not None:
            raw_generic = df[generic_code_col].map(_code_digits).astype("string")
            generic_len = raw_generic.str.len()
            is_district_code = generic_len.ge(5)
            is_municipality_code = generic_len.between(1, 4)

            fill_muni = out["kommun_kod"].isna() & is_municipality_code
            out.loc[fill_muni, "kommun_kod"] = df.loc[fill_muni, generic_code_col].map(_municipality_code)

            fill_district = out["valdistrikt_kod"].isna() & is_district_code
            out.loc[fill_district, "valdistrikt_kod"] = df.loc[fill_district, generic_code_col].map(_district_code)

            fill_from_district = out["kommun_kod"].isna() & is_district_code
            out.loc[fill_from_district, "kommun_kod"] = df.loc[fill_from_district, generic_code_col].map(
                lambda x: _municipality_code(x, from_district=True)
            )

        valid = (
            out["kommun_kod"].astype(str).str.fullmatch(r"\d{4}", na=False)
            & out["turnout"].between(0, 100, inclusive="both")
        )
        out = out[valid].copy()
        if out.empty:
            continue

        row_is_district = out["valdistrikt_kod"].notna()
        row_is_municipality = ~row_is_district

        if level_hint == "district":
            row_is_district[:] = True
            row_is_municipality[:] = False
        elif level_hint == "municipality":
            row_is_municipality[:] = True
            row_is_district[:] = False
        elif "valdistrikt" in sheet_norm:
            row_is_district[:] = True
            row_is_municipality[:] = False
        elif "kommun" in sheet_norm and "valdistrikt" not in sheet_norm:
            row_is_municipality[:] = True
            row_is_district[:] = False

        if row_is_district.any():
            district_frames.append(out[row_is_district].copy())
        if row_is_municipality.any():
            municipality_frames.append(out[row_is_municipality].copy())

        print(
            f"Turnout sheet {sheet!r}: rows={len(out)}, "
            f"municipality_rows={int(row_is_municipality.sum())}, "
            f"district_rows={int(row_is_district.sum())}, "
            f"turnout_col={turnout_col!r}, generic_code_col={generic_code_col!r}"
        )

    return municipality_frames, district_frames



def _turnout_rows_from_pivot_workbook(
    content: bytes,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    """
    Parse Valmyndigheten's 2022/2026 pivot-style workbooks.

    Riksdagsfiler use roster_RD and kommunvalsfiler use roster_KF. The raw
    roster sheet supplies municipality/district identity; the Valdeltagande
    sheet supplies hierarchical turnout totals.
    """
    xl = pd.ExcelFile(io.BytesIO(content))
    roster_sheets = [
        name for name in xl.sheet_names
        if _norm_header(name).startswith("roster")
    ]
    turnout_sheet = next(
        (name for name in xl.sheet_names if _norm_header(name) == "valdeltagande"),
        None,
    )
    if not roster_sheets or turnout_sheet is None:
        print(
            f"Turnout pivot parser: missing roster/turnout sheet. "
            f"sheets={xl.sheet_names}"
        )
        return [], []

    roster_sheet = roster_sheets[0]
    roster = pd.read_excel(io.BytesIO(content), sheet_name=roster_sheet, header=0)
    cols = {c: _norm_header(c) for c in roster.columns}

    kommun_col = next((c for c,n in cols.items() if n == "kommun"), None)
    district_code_col = next((c for c,n in cols.items() if "valdistriktskod" in n), None)
    district_name_col = next((c for c,n in cols.items() if "valdistriktsnamn" in n), None)

    # Known Valmyndigheten roster layout fallback:
    # Val, Distrikt, Län, Region, Kommun, Valdistriktskod, Valdistriktsnamn, ...
    if len(roster.columns) >= 7:
        kommun_col = kommun_col if kommun_col is not None else roster.columns[4]
        district_code_col = district_code_col if district_code_col is not None else roster.columns[5]
        district_name_col = district_name_col if district_name_col is not None else roster.columns[6]

    if kommun_col is None or district_code_col is None or district_name_col is None:
        print(
            f"Turnout pivot parser ({roster_sheet}): geography columns missing; "
            f"columns={list(roster.columns)}"
        )
        return [], []

    base = roster[[kommun_col, district_code_col, district_name_col]].dropna().copy()
    base["kommun"] = base[kommun_col].astype(str).str.strip()
    base["valdistrikt_kod"] = base[district_code_col].map(_district_code).astype("string")
    base["kommun_kod"] = base[district_code_col].map(
        lambda x: _municipality_code(x, from_district=True)
    ).astype("string")
    base["valdistrikt_namn"] = base[district_name_col].astype(str).str.strip()
    base = base[
        base["kommun_kod"].str.fullmatch(r"\d{4}", na=False)
        & base["valdistrikt_kod"].notna()
    ].drop_duplicates(["kommun_kod", "valdistrikt_kod"])

    def key(x: object) -> str:
        return _norm_header(x)

    municipality_codes_by_name = {}
    for kommun, g in base.groupby("kommun"):
        codes = [
            x for x in g["kommun_kod"].dropna().astype(str).unique()
            if re.fullmatch(r"\d{4}", x)
        ]
        if len(codes) == 1:
            municipality_codes_by_name[key(kommun)] = codes[0]

    district_lookup = {}
    for row in base.itertuples(index=False):
        district_lookup[(key(row.kommun), key(row.valdistrikt_namn))] = (
            str(row.kommun_kod),
            str(row.valdistrikt_kod),
        )

    raw = pd.read_excel(io.BytesIO(content), sheet_name=turnout_sheet, header=None)

    header_row = None
    label_idx = None
    votes_idx = None
    eligible_idx = None
    for i in range(min(25, len(raw))):
        vals = [_norm_header(x) for x in raw.iloc[i].tolist()]
        if any("radetiketter" in v for v in vals):
            header_row = i
            label_idx = next((j for j,v in enumerate(vals) if "radetiketter" in v), 0)
            votes_idx = next(
                (j for j,v in enumerate(vals) if "summaavroster" in v or v == "roster"),
                1,
            )
            eligible_idx = next(
                (j for j,v in enumerate(vals) if "rostberattig" in v),
                2,
            )
            break

    if header_row is None:
        print(
            f"Turnout pivot parser ({roster_sheet}): no Radetiketter header "
            f"found in {turnout_sheet}"
        )
        return [], []

    body = raw.iloc[header_row + 1:].copy()
    municipality_rows = []
    district_rows = []
    current_muni_name = None
    current_muni_code = None

    for _, r in body.iterrows():
        label_val = r.iloc[label_idx] if label_idx is not None and label_idx < len(r) else np.nan
        label = str(label_val).strip() if pd.notna(label_val) else ""
        if not label or label.lower() == "nan":
            continue

        votes_val = r.iloc[votes_idx] if votes_idx is not None and votes_idx < len(r) else np.nan
        eligible_val = r.iloc[eligible_idx] if eligible_idx is not None and eligible_idx < len(r) else np.nan
        votes = pd.to_numeric(pd.Series([votes_val]), errors="coerce").iloc[0]
        eligible = pd.to_numeric(pd.Series([eligible_val]), errors="coerce").iloc[0]
        label_key = key(label)

        # A polling district can have exactly the same name as its municipality
        # (notably Bjurholm and Arjeplog in the 2022 parliamentary workbook).
        # In the pivot hierarchy the municipality subtotal comes first and the
        # same-named district follows.  Once a municipality context is active,
        # prefer an exact district lookup before interpreting the repeated label
        # as another municipality subtotal.
        same_name_district = None
        if current_muni_name is not None and current_muni_code is not None:
            same_name_district = district_lookup.get(
                (key(current_muni_name), label_key)
            )

        if (
            same_name_district is not None
            and label_key == key(current_muni_name)
        ):
            kommun_kod, district_code = same_name_district
            if pd.notna(votes) and pd.notna(eligible) and float(eligible) > 0:
                turnout = 100 * float(votes) / float(eligible)
                if 0 <= turnout <= 100:
                    district_rows.append({
                        "kommun_kod": kommun_kod,
                        "kommun": current_muni_name,
                        "turnout": turnout,
                        "rostberattigade": float(eligible),
                        "valdistrikt_kod": district_code,
                    })
            continue

        if label_key in municipality_codes_by_name:
            current_muni_name = label
            current_muni_code = municipality_codes_by_name[label_key]
            if pd.notna(votes) and pd.notna(eligible) and float(eligible) > 0:
                municipality_rows.append({
                    "kommun_kod": current_muni_code,
                    "kommun": current_muni_name,
                    "turnout": 100 * float(votes) / float(eligible),
                    "rostberattigade": float(eligible),
                    "valdistrikt_kod": pd.NA,
                })
            continue

        if current_muni_name is None or current_muni_code is None:
            continue

        found = district_lookup.get((key(current_muni_name), label_key))
        if found is None:
            continue
        kommun_kod, district_code = found
        if pd.isna(votes) or pd.isna(eligible) or float(eligible) <= 0:
            continue

        turnout = 100 * float(votes) / float(eligible)
        if not (0 <= turnout <= 100):
            continue

        district_rows.append({
            "kommun_kod": kommun_kod,
            "kommun": current_muni_name,
            "turnout": turnout,
            "rostberattigade": float(eligible),
            "valdistrikt_kod": district_code,
        })

    muni = pd.DataFrame(municipality_rows)
    districts = pd.DataFrame(district_rows)
    if not muni.empty:
        muni["kommun_kod"] = muni["kommun_kod"].astype("string")
        muni["valdistrikt_kod"] = muni["valdistrikt_kod"].astype("string")
    if not districts.empty:
        districts["kommun_kod"] = districts["kommun_kod"].astype("string")
        districts["valdistrikt_kod"] = districts["valdistrikt_kod"].astype("string")

    print(
        f"Turnout pivot parser ({roster_sheet}): "
        f"roster municipalities={len(municipality_codes_by_name)}, "
        f"municipalities={muni['kommun_kod'].nunique() if not muni.empty else 0}, "
        f"district municipalities={districts['kommun_kod'].nunique() if not districts.empty else 0}, "
        f"district rows={len(districts)}, "
        f"header_row={header_row}, votes_col={votes_idx}, eligible_col={eligible_idx}"
    )
    return ([muni] if not muni.empty else []), ([districts] if not districts.empty else [])


def get_turnout_series() -> pd.DataFrame:
    """
    Municipal turnout and within-municipality turnout gap in Swedish parliamentary
    elections (riksdagsval). Election-year observations are linearly interpolated
    between 2018, 2022 and 2026 for explanatory analysis. The sub-municipal gap
    is based on polling districts (valdistrikt), not DeSO. These interpolated variables are excluded
    from out-of-sample validation to avoid using a future election endpoint.
    """
    pop_meta = metadata(POPULATION_URL)
    pop_region = find_var(pop_meta, "region")
    official_municipalities = {
        _municipality_code(v)
        for v in municipality_codes(pop_region)
    }
    official_municipalities = {x for x in official_municipalities if isinstance(x, str)}

    election_rows = []

    for election_year, sources in TURNOUT_SOURCES.items():
        muni_frames = []
        district_frames = []

        if "municipality" in sources:
            content = _excel_bytes(_resolve_external_file(sources["municipality"]))
            m, d = _turnout_rows_from_workbook(content, level_hint="municipality")
            muni_frames.extend(m)
            district_frames.extend(d)

        if "district" in sources:
            content = _excel_bytes(_resolve_external_file(sources["district"]))
            m, d = _turnout_rows_from_workbook(content, level_hint="district")
            muni_frames.extend(m)
            district_frames.extend(d)

        debug_content = None
        if "combined" in sources:
            content = _excel_bytes(_resolve_external_file(sources["combined"]))
            debug_content = content
            m, d = _turnout_rows_from_workbook(content, level_hint=None)
            if not m or not d:
                pm, pdist = _turnout_rows_from_pivot_workbook(content)
                if pm:
                    m = pm
                if pdist:
                    d = pdist
            muni_frames.extend(m)
            district_frames.extend(d)

        muni = pd.concat(muni_frames, ignore_index=True) if muni_frames else pd.DataFrame()
        districts = pd.concat(district_frames, ignore_index=True) if district_frames else pd.DataFrame()

        if not muni.empty:
            muni = muni[muni["kommun_kod"].isin(official_municipalities)].copy()
        if not districts.empty:
            districts = districts[districts["kommun_kod"].isin(official_municipalities)].copy()

        # Municipality turnout must come from the official municipality total
        # whenever it exists.  Reconstructing it from geographic polling
        # districts can undercount late/collection-district votes that have no
        # separate eligible-voter denominator.  District rows are therefore
        # used for the within-municipality gap, while reconstruction is only a
        # fallback when an explicit municipality total is genuinely absent.
        if not districts.empty and districts["rostberattigade"].notna().any():
            explicit_muni = muni.copy()
            tmp = districts.dropna(subset=["rostberattigade"]).copy()
            tmp["weighted"] = tmp["turnout"] * tmp["rostberattigade"]
            district_muni = (
                tmp.groupby("kommun_kod", as_index=False)
                .agg(weighted=("weighted", "sum"), rostberattigade=("rostberattigade", "sum"))
            )
            district_muni["turnout"] = (
                district_muni["weighted"] / district_muni["rostberattigade"].replace(0, np.nan)
            )
            district_muni["kommun"] = np.nan

            if explicit_muni.empty:
                muni = district_muni
            else:
                explicit = explicit_muni[
                    ["kommun_kod", "kommun", "turnout", "rostberattigade"]
                ].copy()
                explicit["_priority"] = 1
                district_fallback = district_muni[
                    ["kommun_kod", "kommun", "turnout", "rostberattigade"]
                ].copy()
                district_fallback["_priority"] = 0
                combined = pd.concat(
                    [explicit, district_fallback],
                    ignore_index=True,
                    sort=False,
                )
                muni = (
                    combined.sort_values("_priority", ascending=False)
                    .drop_duplicates("kommun_kod")
                    .drop(columns=["_priority"], errors="ignore")
                )

        if muni.empty or districts.empty:
            print(
                f"Turnout {election_year} after official-code filter: "
                f"municipality_rows={len(muni)}, district_rows={len(districts)}"
            )
            if muni_frames:
                sample_muni = pd.concat(muni_frames, ignore_index=True)["kommun_kod"].dropna().astype(str).unique()[:12]
                print(f"Turnout {election_year} municipality-code sample before filter: {sample_muni.tolist()}")
            if district_frames:
                sample_dist = pd.concat(district_frames, ignore_index=True)["kommun_kod"].dropna().astype(str).unique()[:12]
                print(f"Turnout {election_year} district-derived municipality-code sample before filter: {sample_dist.tolist()}")
            if debug_content is not None:
                _debug_turnout_workbook(debug_content, election_year)
            raise ValueError(
                f"Turnout parser could not identify both municipality and district data for {election_year}. "
                f"municipality_frames={len(muni_frames)}, district_frames={len(district_frames)}"
            )

        muni_agg = (
            muni.groupby("kommun_kod", as_index=False)
            .agg(valdeltagande_pct=("turnout", "mean"))
        )
        gap = (
            districts.groupby("kommun_kod", as_index=False)["turnout"]
            .agg(["min", "max"])
            .reset_index()
        )
        gap["valdeltagande_gap_pp"] = gap["max"] - gap["min"]
        annual = muni_agg.merge(
            gap[["kommun_kod", "valdeltagande_gap_pp"]],
            on="kommun_kod",
            how="inner",
        )
        annual["election_year"] = election_year

        n_muni = int(muni_agg["kommun_kod"].nunique())
        n_district_muni = int(gap["kommun_kod"].nunique())
        n_merged = int(annual["kommun_kod"].nunique())
        missing_from_district_all = sorted(
            set(muni_agg["kommun_kod"]) - set(gap["kommun_kod"])
        )
        print(
            f"Turnout {election_year} parse counts: municipality={n_muni}, "
            f"district municipalities={n_district_muni}, merged={n_merged}"
        )
        # Diagnostic only: large differences are expected when a municipality
        # has collection/late-count votes outside the geographic district rows.
        if (
            'explicit_muni' in locals()
            and not explicit_muni.empty
            and 'district_muni' in locals()
            and not district_muni.empty
        ):
            turnout_check = explicit_muni[
                ["kommun_kod", "turnout"]
            ].drop_duplicates("kommun_kod").merge(
                district_muni[["kommun_kod", "turnout"]].drop_duplicates("kommun_kod"),
                on="kommun_kod",
                how="inner",
                suffixes=("_official", "_district_reconstructed"),
            )
            if not turnout_check.empty:
                turnout_check["abs_diff_pp"] = (
                    turnout_check["turnout_official"]
                    - turnout_check["turnout_district_reconstructed"]
                ).abs()
                print(
                    f"Turnout {election_year} official-vs-district reconstruction: "
                    f"max abs diff={turnout_check['abs_diff_pp'].max():.3f} pp"
                )
        if missing_from_district_all:
            print(
                f"Turnout {election_year} municipalities without district gap: "
                f"{missing_from_district_all}"
            )
        if n_merged < 280:
            missing_from_district = missing_from_district_all[:15]
            missing_from_muni = sorted(set(gap["kommun_kod"]) - set(muni_agg["kommun_kod"]))[:15]
            raise ValueError(
                f"Turnout {election_year}: parsed only {n_merged} municipalities. "
                f"Missing district examples={missing_from_district}; "
                f"missing municipality examples={missing_from_muni}"
            )

        election_rows.append(annual)
        print(f"Turnout {election_year}: {annual['kommun_kod'].nunique():,} municipalities")

    elections = pd.concat(election_rows, ignore_index=True)
    years = sorted(set(AUX_YEARS))
    out = []
    for kommun_kod, g in elections.groupby("kommun_kod"):
        g = g.sort_values("election_year")
        xs = g["election_year"].to_numpy(dtype=float)
        if len(xs) < 2:
            continue
        for year in years:
            row = {"kommun_kod": kommun_kod, "year": year}
            for metric in ["valdeltagande_pct", "valdeltagande_gap_pp"]:
                ys = g[metric].to_numpy(dtype=float)
                if year < xs.min() or year > xs.max():
                    row[metric] = np.nan
                else:
                    row[metric] = float(np.interp(year, xs, ys))
            row["valdeltagande_interpolerad"] = year not in set(g["election_year"].astype(int))
            out.append(row)

    result = pd.DataFrame(out)
    print(
        f"Turnout interpolated series: {result['kommun_kod'].nunique():,} municipalities, "
        f"{result['year'].min()}–{result['year'].max()}"
    )
    return result


def get_socioeconomic_gap() -> pd.DataFrame:
    """
    Within-municipality spread in the share with low economic standard across
    DeSO areas: max DeSO share minus min DeSO share, in percentage points.
    """
    meta = metadata(INEQUALITY_URL)
    region = find_var(meta, "region")
    age = find_var(meta, "ålder", "alder")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time_var = find_var(meta, "år", "tid")

    low_code = code_for_all_text(content, "låg", "ekonomisk", "standard")
    age_code = code_for_text(age, "totalt")

    deso_values = []
    for value, label in zip(region["values"], region.get("valueTexts", region["values"])):
        text = f"{value} {label}"
        if re.search(r"\d{4}[ABC]\d{4}", text):
            deso_values.append(str(value))

    if len(deso_values) < 5000:
        raise ValueError(
            f"Could identify only {len(deso_values)} DeSO selectors in income table"
        )

    rows = []
    for year in AUX_YEARS:
        df = px_csv(INEQUALITY_URL, {
            region["code"]: deso_values,
            age["code"]: [age_code],
            content["code"]: [low_code],
            time_var["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        region_col = dims.get("region")
        if region_col is None:
            raise ValueError(f"DeSO income response lacks region column for {year}")

        # PxWeb commonly puts both the measure name and selected year in the
        # value-column header, e.g. "Låg ekonomisk standard, procent 2018".
        # Identify this measure explicitly before falling back to the generic
        # dimension/value inference.  This also protects against a descriptive
        # measure header being mistaken for the time dimension.
        value_col = next(
            (
                c for c in df.columns
                if "låg ekonomisk standard" in str(c).strip().lower()
                or "lag ekonomisk standard" in str(c).strip().lower()
            ),
            None,
        )
        if value_col is None:
            value_col = value_column(df, dims)
        df["low_pct"] = normalize_number(df[value_col])
        df["deso"] = df[region_col].astype(str).str.extract(
            r"(\d{4}[ABC]\d{4})", expand=False
        )
        df["kommun_kod"] = df["deso"].str[:4]
        valid = df.dropna(subset=["low_pct", "deso"]).copy()

        agg = (
            valid.groupby("kommun_kod", as_index=False)
            .agg(
                deso_low_min=("low_pct", "min"),
                deso_low_max=("low_pct", "max"),
                antal_deso=("deso", "nunique"),
            )
        )
        agg["ekonomisk_standard_gap_pp"] = agg["deso_low_max"] - agg["deso_low_min"]
        agg["year"] = year
        if agg["kommun_kod"].nunique() < 280:
            raise ValueError(
                f"Socioeconomic gap {year}: only {agg['kommun_kod'].nunique()} municipalities"
            )
        rows.append(agg[["kommun_kod", "year", "ekonomisk_standard_gap_pp", "antal_deso"]])
        print(f"Socioeconomic gap {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)

def get_housing() -> pd.DataFrame:
    """
    Share of all dwelling units that are located in small houses.
    SCB table BO0104T04: small houses / (small houses + apartment buildings
    + other buildings + special dwellings), summed across tenure forms.
    """
    meta = metadata(HOUSING_URL)
    region = find_var(meta, "region")
    house_type = find_var(meta, "hustyp")
    tenure = find_var(meta, "upplåtelseform", "upplatelseform")
    time = find_var(meta, "år", "tid")

    content = None
    try:
        content = find_var(meta, "tabellinnehåll", "contentscode")
    except KeyError:
        pass

    munis = municipality_codes(region)
    small_code = exact_or_contains_code(house_type, "småhus")
    house_codes = list(house_type["values"])
    tenure_codes = list(tenure["values"])

    rows = []
    for year in AUX_YEARS:
        selections = {
            region["code"]: munis,
            house_type["code"]: house_codes,
            tenure["code"]: tenure_codes,
            time["code"]: [str(year)],
        }
        if content is not None:
            selections[content["code"]] = [content["values"][0]]

        df = px_csv(HOUSING_URL, selections)
        dims = standardize_columns(df)

        for c in df.columns:
            cl = str(c).lower()
            if "hustyp" in cl:
                dims["house_type"] = c
            elif "upplåtelseform" in cl or "upplatelseform" in cl:
                dims["tenure"] = c

        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(
                f"Expected one housing value column for {year}, got {value_cols}; "
                f"columns={list(df.columns)}"
            )

        df["value"] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )

        hcol = dims["house_type"]
        tcol = dims["tenure"]
        df["_is_small"] = df[hcol].astype(str).str.lower().str.contains(
            "småhus", regex=False
        )
        tenure_text = df[tcol].astype(str).str.lower()
        df["_is_rental"] = tenure_text.str.contains("hyres", regex=False)
        df["_is_condo"] = tenure_text.str.contains("bostadsr", regex=False)

        totals = (
            df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": "bostader_totalt"})
        )
        small = (
            df[df["_is_small"]]
            .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": "bostader_smahus"})
        )
        rental = (
            df[df["_is_rental"]]
            .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": "bostader_hyresratt"})
        )
        condo = (
            df[df["_is_condo"]]
            .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": "bostader_bostadsratt"})
        )

        agg = totals.merge(
            small,
            on=["kommun_kod", "kommun", "year"],
            how="left",
        ).merge(
            rental,
            on=["kommun_kod", "kommun", "year"],
            how="left",
        ).merge(
            condo,
            on=["kommun_kod", "kommun", "year"],
            how="left",
        )
        for col in ["bostader_smahus", "bostader_hyresratt", "bostader_bostadsratt"]:
            agg[col] = agg[col].fillna(0)
        agg["andel_smahus"] = (
            100 * agg["bostader_smahus"] / agg["bostader_totalt"].replace(0, np.nan)
        )
        agg["andel_hyresratt"] = (
            100 * agg["bostader_hyresratt"] / agg["bostader_totalt"].replace(0, np.nan)
        )
        agg["andel_bostadsratt"] = (
            100 * agg["bostader_bostadsratt"] / agg["bostader_totalt"].replace(0, np.nan)
        )
        rows.append(agg[[
            "kommun_kod", "kommun", "year",
            "bostader_smahus", "bostader_totalt", "andel_smahus",
            "andel_hyresratt", "andel_bostadsratt"
        ]])
        print(f"Housing {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)


def get_completed_housing() -> pd.DataFrame:
    """
    Completed dwellings in newly constructed buildings by municipality and year.
    SCB table LghReHtypUfAr.  House type and tenure categories are mutually
    exclusive, so summing them gives the municipality total for each year.
    """
    meta = metadata(COMPLETED_HOUSING_URL)
    region = find_var(meta, "region")
    house_type = find_var(meta, "hustyp")
    tenure = find_var(meta, "upplåtelseform", "upplatelseform")
    time = find_var(meta, "år", "tid")

    content = None
    try:
        content = find_var(meta, "tabellinnehåll", "contentscode")
    except KeyError:
        pass

    munis = municipality_codes(region)
    rows = []
    for year in AUX_YEARS:
        selections = {
            region["code"]: munis,
            house_type["code"]: list(house_type["values"]),
            tenure["code"]: list(tenure["values"]),
            time["code"]: [str(year)],
        }
        if content is not None:
            selections[content["code"]] = [content["values"][0]]

        df = px_csv(COMPLETED_HOUSING_URL, selections)
        dims = standardize_columns(df)
        for c in df.columns:
            cl = str(c).lower()
            if "hustyp" in cl:
                dims["house_type"] = c
            elif "upplåtelseform" in cl or "upplatelseform" in cl:
                dims["tenure"] = c

        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(
                f"Expected one completed-housing value column for {year}, got {value_cols}; "
                f"columns={list(df.columns)}"
            )

        df["value"] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )
        agg = (
            df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum(min_count=1)
            .rename(columns={"value": "fardigstallda_bostader"})
        )
        if agg["kommun_kod"].nunique() < 280:
            raise ValueError(
                f"Completed housing {year}: only {agg['kommun_kod'].nunique()} municipalities"
            )
        rows.append(agg)
        print(f"Completed housing {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)


def get_leisure_houses() -> pd.DataFrame:
    """SCB annual leisure-house stock by municipality."""
    leisure_url, meta = resolve_leisure_house_url()
    region = find_var(meta, "region")
    time_var = find_var(meta, "år", "tid")
    munis = municipality_codes(region)
    available_years = {str(v) for v in time_var["values"]}
    rows = []

    for year in AUX_YEARS:
        if str(year) not in available_years:
            continue
        df = px_csv(leisure_url, {
            region["code"]: munis,
            time_var["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        value_cols = [c for c in df.columns if c not in set(dims.values())]
        if len(value_cols) != 1:
            raise ValueError(f"Expected one leisure-house value column for {year}, got {value_cols}")
        df["fritidshus"] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )
        agg = (
            df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["fritidshus"]
            .sum()
        )
        rows.append(agg)
        print(f"Leisure houses {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)


def _normalize_place_name(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\bkommun\b", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def get_crime_total() -> pd.DataFrame:
    """
    Total reported crimes per 100,000 inhabitants from the user's national
    BRÅ annual dataset. Category 5036 is 'Totalt antal brott'.
    """
    rows = []
    for year in AUX_YEARS:
        url = BRA_ANNUAL_RAW.format(year=year)
        try:
            df = pd.read_parquet(url, columns=["År", "Kommun", "Brott_ID", "Per100000"])
        except Exception as exc:
            raise RuntimeError(f"Could not read BRÅ annual parquet for {year}: {exc}") from exc

        df["Brott_ID"] = pd.to_numeric(df["Brott_ID"], errors="coerce")
        df = df[df["Brott_ID"] == 5036].copy()
        df["brott_per_100000"] = pd.to_numeric(df["Per100000"], errors="coerce")
        df["year"] = year
        df["kommun_nyckel"] = df["Kommun"].map(_normalize_place_name)

        agg = (
            df.groupby(["kommun_nyckel", "year"], as_index=False)["brott_per_100000"]
            .mean()
        )
        if len(agg) < 280:
            raise ValueError(f"BRÅ total crime {year}: only {len(agg)} municipalities")
        rows.append(agg)
        print(f"BRÅ total crime {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)

def get_labor_market() -> pd.DataFrame:
    """
    Annual municipal labor-market indicators from SCB BAS.
    Uses the official annual table 2020-2025 and requests the total categories
    for sex and birth region plus age 20-64 years.
    """
    meta = metadata(LABOR_URL)
    region = find_var(meta, "region")
    sex = find_var(meta, "kön", "kon")
    age = find_var(meta, "ålder", "alder")
    birth_region = find_var(meta, "födelseregion", "fodelseregion")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    sex_codes = aggregate_codes(sex)
    birth_codes = aggregate_codes(birth_region)
    age_code = code_for_all_text(age, "20", "64")

    employment_rate_code = code_for_text(content, "sysselsättningsgrad")
    unemployment_rate_code = code_for_text(content, "arbetslöshet")

    def fetch_measure(year: int, measure_code: str, out_name: str) -> pd.DataFrame:
        df = px_csv(LABOR_URL, {
            region["code"]: munis,
            sex["code"]: sex_codes,
            age["code"]: [age_code],
            birth_region["code"]: birth_codes,
            content["code"]: [measure_code],
            time["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        # Birth region is a dimension in this table.
        for c in df.columns:
            cl = str(c).lower()
            if "födelseregion" in cl or "fodelseregion" in cl:
                dims["birth_region"] = c

        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(
                f"Expected one labor value column for {year}/{out_name}, got {value_cols}; "
                f"columns={list(df.columns)}"
            )

        df[out_name] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )
        # If the table lacks an explicit total for sex or birth region,
        # aggregate components by mean only when the returned rate is identical
        # across duplicated dimensions; normally aggregate_codes selects total.
        out = df.groupby(["kommun_kod", "kommun", "year"], as_index=False)[out_name].mean()
        return out

    rows = []
    for year in AUX_YEARS:
        if year < 2020 or year > 2024:
            continue
        employed = fetch_measure(year, employment_rate_code, "sysselsattningsgrad")
        unemployed = fetch_measure(year, unemployment_rate_code, "arbetsloshet")
        agg = employed.merge(
            unemployed,
            on=["kommun_kod", "kommun", "year"],
            how="inner",
        )
        rows.append(agg)
        print(f"Labor market {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)


def get_education() -> pd.DataFrame:
    """
    Share of residents aged 25-64 with post-secondary education.
    Uses SCB's official education-register municipality table.
    """
    meta = metadata(EDUCATION_URL)
    region = find_var(meta, "region")
    age = find_var(meta, "ålder", "alder")
    education = find_var(meta, "utbildningsnivå", "utbildningsniva")
    sex = find_var(meta, "kön", "kon")
    content = find_var(meta, "tabellinnehåll", "contentscode")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    sex_codes = aggregate_codes(sex)

    age_codes = []
    for code, text in zip(age["values"], age.get("valueTexts", age["values"])):
        a = age_numeric(text)
        if np.isfinite(a) and 25 <= a <= 64:
            age_codes.append(code)
    if not age_codes:
        raise ValueError(
            f"No education age codes identified for 25-64. "
            f"Sample={list(zip(age['values'][:20], age.get('valueTexts', age['values'])[:20]))}"
        )

    edu_pairs = list(zip(
        education["values"],
        education.get("valueTexts", education["values"])
    ))
    postsecondary_codes = [
        code for code, text in edu_pairs
        if ("eftergymnasial" in str(text).lower() or "forskarutbild" in str(text).lower())
    ]
    if not postsecondary_codes:
        raise ValueError(
            f"No post-secondary education categories found: {[t for _, t in edu_pairs]}"
        )

    total_edu_codes = aggregate_codes(education)
    has_explicit_total = len(total_edu_codes) == 1 and total_edu_codes[0] not in postsecondary_codes
    if has_explicit_total:
        requested_edu_codes = list(dict.fromkeys(postsecondary_codes + total_edu_codes))
    else:
        requested_edu_codes = [code for code, _ in edu_pairs]

    count_code = code_for_text(content, "Antal")
    rows = []
    chunk_size = 40
    for year in AUX_YEARS:
        year_parts = []
        for i in range(0, len(munis), chunk_size):
            muni_chunk = munis[i:i + chunk_size]
            df = px_csv(EDUCATION_URL, {
                region["code"]: muni_chunk,
                age["code"]: age_codes,
                education["code"]: requested_edu_codes,
                sex["code"]: sex_codes,
                content["code"]: [count_code],
                time["code"]: [str(year)],
            })
            dims = standardize_columns(df)
            dim_cols = set(dims.values())
            value_cols = [c for c in df.columns if c not in dim_cols]
            if len(value_cols) != 1:
                raise ValueError(
                    f"Expected one education value column for {year}, got {value_cols}; "
                    f"columns={list(df.columns)}"
                )

            df["value"] = normalize_number(df[value_cols[0]])
            df["year"] = year
            df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
                lambda x: pd.Series(split_region(x))
            )
            year_parts.append(df)

        df = pd.concat(year_parts, ignore_index=True)
        ecol = dims["education"]
        df["_postsecondary"] = df[ecol].astype(str).str.lower().apply(
            lambda x: ("eftergymnasial" in x) or ("forskarutbild" in x)
        )

        numerator = (
            df[df["_postsecondary"]]
            .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": "eftergymnasial"})
        )

        if has_explicit_total:
            total_labels = {
                str(text).strip().lower()
                for code, text in edu_pairs
                if code in total_edu_codes
            }
            denominator = (
                df[df[ecol].astype(str).str.strip().str.lower().isin(total_labels)]
                .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
                .sum()
                .rename(columns={"value": "utbildning_total"})
            )
        else:
            denominator = (
                df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
                .sum()
                .rename(columns={"value": "utbildning_total"})
            )

        agg = denominator.merge(
            numerator,
            on=["kommun_kod", "kommun", "year"],
            how="left",
        )
        agg["andel_eftergymnasial"] = (
            100 * agg["eftergymnasial"] / agg["utbildning_total"].replace(0, np.nan)
        )
        rows.append(agg[[
            "kommun_kod", "kommun", "year", "andel_eftergymnasial"
        ]])
        print(f"Education {year}: {len(agg):,} municipalities")

    return pd.concat(rows, ignore_index=True)


def get_students() -> pd.DataFrame:
    """
    Share of the population aged 20-64 who are students.
    SCB table IntGr8Kom1N already reports the measure as percent.
    Only years actually available in the table are requested.
    """
    meta = metadata(STUDENT_URL)
    region = find_var(meta, "region")
    background = find_var(meta, "bakgrund")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    background_code = code_for_all_text(background, "samtliga", "20", "64")
    available_years = {str(v) for v in time["values"]}

    rows = []
    for year in AUX_YEARS:
        if str(year) not in available_years:
            continue

        selections = {
            region["code"]: munis,
            background["code"]: [background_code],
            time["code"]: [str(year)],
        }

        # Some PxWeb tables expose an explicit content dimension, others encode
        # the single measure directly in the returned value-column heading.
        try:
            content = find_var(meta, "tabellinnehåll", "contentscode")
            selections[content["code"]] = [content["values"][0]]
        except KeyError:
            pass

        df = px_csv(STUDENT_URL, selections)

        dims = standardize_columns(df)
        for c in df.columns:
            cl = str(c).lower()
            if "bakgrund" in cl:
                dims["background"] = c

        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(
                f"Expected one student-share value column for {year}, got {value_cols}; "
                f"columns={list(df.columns)}"
            )

        df["andel_studerande"] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )

        agg = (
            df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["andel_studerande"]
            .mean()
        )
        rows.append(agg)
        print(f"Students {year}: {len(agg):,} municipalities")

    if not rows:
        raise ValueError(
            f"No student-share years available for AUX_YEARS={AUX_YEARS}; "
            f"table years={list(time['values'])[-10:]}"
        )

    return pd.concat(rows, ignore_index=True)


def get_industry_structure() -> pd.DataFrame:
    """
    Employment structure by workplace location, ages 15-74.
    Three candidate shares of total employed persons:
      B+C manufacturing/mining,
      I hotels/restaurants,
      R+S+T+U culture/recreation/other services.
    SCB ArRegUtb, annual register 2020-2024.
    """
    meta = metadata(INDUSTRY_URL)
    content = find_var(meta, "tabellinnehåll", "contentscode")
    region = find_var(meta, "region")
    sex = find_var(meta, "kön", "kon")
    industry = find_var(meta, "näringsgren", "naringsgren")
    education = find_var(meta, "utbildningsnivå", "utbildningsniva")
    time = find_var(meta, "år", "tid")

    munis = municipality_codes(region)
    sex_codes = aggregate_codes(sex)
    education_codes = list(education["values"])
    workplace_code = code_for_all_text(content, "arbetsställets", "belägenhet")

    industry_pairs = list(zip(
        industry["values"],
        industry.get("valueTexts", industry["values"])
    ))

    def industry_code(code_needles=(), text_needles=()):
        code_needles_l = [str(x).lower() for x in code_needles]
        text_needles_l = [str(x).lower() for x in text_needles]
        for code, text in industry_pairs:
            c = str(code).strip().lower()
            t = str(text).strip().lower()
            if (
                all(n in c for n in code_needles_l)
                and all(n in t for n in text_needles_l)
            ):
                return code
        raise KeyError(
            f"Industry category not found. code_needles={code_needles}, "
            f"text_needles={text_needles}, "
            f"sample={[(str(c), str(t)) for c, t in industry_pairs[:20]]}"
        )

    total_industry_code = None
    for code, text in industry_pairs:
        c = str(code).strip().lower()
        t = str(text).strip().lower()
        if (
            ("a-u+us" in c or "a–u+us" in c or "a-u" in c or "a–u" in c)
            and ("total" in t or "totalt" in t or "+us" in c or " us" in t)
        ):
            total_industry_code = code
            break

    industry_bc = industry_code(code_needles=("b+c",))
    industry_i = industry_code(code_needles=("i",), text_needles=("hotell",))
    industry_rstu = industry_code(code_needles=("r+s+t+u",))

    if total_industry_code is not None:
        wanted = [total_industry_code, industry_bc, industry_i, industry_rstu]
    else:
        # No explicit total category: request all industry groups and sum them.
        wanted = list(industry["values"])
    label_map = dict(zip(
        [str(v) for v in industry["values"]],
        [str(t) for t in industry.get("valueTexts", industry["values"])]
    ))
    available_years = {str(v) for v in time["values"]}

    rows = []
    for year in AUX_YEARS:
        if str(year) not in available_years:
            continue

        df = px_csv(INDUSTRY_URL, {
            content["code"]: [workplace_code],
            region["code"]: munis,
            sex["code"]: sex_codes,
            industry["code"]: wanted,
            education["code"]: education_codes,
            time["code"]: [str(year)],
        })

        dims = standardize_columns(df)
        for c in df.columns:
            cl = str(c).lower()
            if "näringsgren" in cl or "naringsgren" in cl:
                dims["industry"] = c

        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(
                f"Expected one industry value column for {year}, got {value_cols}; "
                f"columns={list(df.columns)}"
            )

        df["value"] = normalize_number(df[value_cols[0]])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(
            lambda x: pd.Series(split_region(x))
        )

        icol = dims["industry"]
        def _match_code(code):
            code_text = str(code).strip().lower()
            label_text = label_map.get(str(code), str(code)).strip().lower()
            combined_text = f"{code_text} {label_text}".strip()
            observed = (
                df[icol].astype(str)
                .str.strip()
                .str.lower()
                .str.replace(r"\s+", " ", regex=True)
            )
            return (
                observed.eq(code_text)
                | observed.eq(label_text)
                | observed.eq(combined_text)
            )

        def _sum_for(code, name):
            matched = df[_match_code(code)].copy()
            if matched.empty:
                observed_values = sorted(df[icol].dropna().astype(str).unique().tolist())[:30]
                raise ValueError(
                    f"No rows matched industry code={code!r}, "
                    f"label={label_map.get(str(code))!r}, "
                    f"observed sample={observed_values}"
                )
            return (
                matched
                .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
                .sum()
                .rename(columns={"value": name})
            )

        if total_industry_code is not None:
            total = _sum_for(total_industry_code, "sysselsatta_totalt")
        else:
            total = (
                df.groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
                .sum()
                .rename(columns={"value": "sysselsatta_totalt"})
            )

        bc = _sum_for(industry_bc, "sysselsatta_industri")
        hosp = _sum_for(industry_i, "sysselsatta_hotell_restaurang")
        rstu = _sum_for(industry_rstu, "sysselsatta_kultur_service")

        agg = total.merge(bc, on=["kommun_kod","kommun","year"], how="left")
        agg = agg.merge(hosp, on=["kommun_kod","kommun","year"], how="left")
        agg = agg.merge(rstu, on=["kommun_kod","kommun","year"], how="left")

        denom = agg["sysselsatta_totalt"].replace(0, np.nan)
        agg["andel_industri_bc"] = 100 * agg["sysselsatta_industri"] / denom
        agg["andel_hotell_restaurang_i"] = 100 * agg["sysselsatta_hotell_restaurang"] / denom
        agg["andel_kultur_service_rstu"] = 100 * agg["sysselsatta_kultur_service"] / denom

        if len(agg) == 0:
            raise ValueError(
                f"Industry aggregation returned 0 municipalities for {year}. "
                f"Industry values sample={sorted(df[icol].dropna().astype(str).unique().tolist())[:30]}"
            )

        rows.append(agg[[
            "kommun_kod","kommun","year",
            "sysselsatta_totalt",
            "andel_industri_bc",
            "andel_hotell_restaurang_i",
            "andel_kultur_service_rstu",
        ]])
        print(f"Industry structure {year}: {len(agg):,} municipalities")

    if not rows:
        raise ValueError(
            f"No industry years available for AUX_YEARS={AUX_YEARS}; "
            f"table years={list(time['values'])}"
        )

    return pd.concat(rows, ignore_index=True)


def get_fa15_membership() -> pd.DataFrame:
    """
    Municipality-to-FA15 mapping from Tillvaxtverket.
    FA15 is used because the model years 2020-2024 fall inside its 2015-2025 period.
    The workbook layout is parsed defensively because presentation headers may change.
    """
    r = session.get(FA15_XLSX_URL, timeout=60)
    if not r.ok:
        raise RuntimeError(
            f"FA15 workbook download failed {r.status_code}: {r.text[:300]}"
        )

    sheets = pd.read_excel(io.BytesIO(r.content), sheet_name=None, header=None, engine="openpyxl")
    candidates = []

    for sheet_name, raw in sheets.items():
        raw = raw.copy()
        for header_row in range(min(20, len(raw))):
            headers = [str(x).strip() if pd.notna(x) else "" for x in raw.iloc[header_row]]
            hl = [x.lower() for x in headers]
            if not any("kommun" in x for x in hl):
                continue
            if not any(("fa" in x and ("region" in x or "15" in x)) for x in hl):
                continue

            data = raw.iloc[header_row + 1:].copy()
            data.columns = headers

            kommun_cols = [c for c in data.columns if "kommun" in str(c).lower()]
            fa_cols = [
                c for c in data.columns
                if "fa" in str(c).lower()
                and ("region" in str(c).lower() or "15" in str(c).lower())
            ]
            if not kommun_cols or not fa_cols:
                continue

            for _, row in data.iterrows():
                kommun_code = None
                kommun_name = None
                for c in kommun_cols:
                    val = str(row[c]).strip() if pd.notna(row[c]) else ""
                    m = re.search(r"(?<!\d)(\d{4})(?!\d)", val)
                    if m and kommun_code is None:
                        kommun_code = m.group(1)
                    elif val and not val.isdigit() and kommun_name is None:
                        kommun_name = val

                # Fallback: municipality code can live in a separate unnamed code column.
                if kommun_code is None:
                    for val in row.tolist():
                        txt = str(val).strip() if pd.notna(val) else ""
                        m = re.fullmatch(r"(\d{4})(?:\.0)?", txt)
                        if m:
                            kommun_code = m.group(1)
                            break

                fa_name = None
                fa_code = None
                for c in fa_cols:
                    val = str(row[c]).strip() if pd.notna(row[c]) else ""
                    if not val:
                        continue
                    if re.fullmatch(r"\d+(?:\.0)?", val):
                        if fa_code is None:
                            fa_code = str(int(float(val)))
                    elif fa_name is None:
                        fa_name = val

                if kommun_code and (fa_name or fa_code):
                    candidates.append({
                        "kommun_kod": kommun_code,
                        "fa15_kod": fa_code,
                        "fa15_namn": fa_name,
                        "_sheet": sheet_name,
                    })

    if not candidates:
        raise ValueError(
            "Could not parse any municipality-to-FA15 rows from Tillvaxtverket workbook"
        )

    fa = pd.DataFrame(candidates)
    fa = fa.sort_values(["kommun_kod", "fa15_namn"], na_position="last")
    fa = fa.drop_duplicates("kommun_kod", keep="first").drop(columns=["_sheet"])

    if fa["kommun_kod"].nunique() < 280:
        raise ValueError(
            f"FA15 mapping parsed only {fa['kommun_kod'].nunique()} municipalities; "
            f"expected close to 290. Sample={fa.head(10).to_dict('records')}"
        )

    # Ensure one stable region key even when one of code/name is absent.
    fa["fa15_id"] = fa["fa15_kod"].fillna("") + "|" + fa["fa15_namn"].fillna("")
    print(f"FA15 membership: {fa['kommun_kod'].nunique():,} municipalities")
    return fa[["kommun_kod", "fa15_id", "fa15_kod", "fa15_namn"]]

def standardize_columns(df: pd.DataFrame) -> dict[str, str]:
    out = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        # More specific dimensions must be tested before generic "region".
        if "födelseregion" in cl or "fodelseregion" in cl:
            out["birth_region"] = c
        elif "region" in cl:
            out["region"] = c
        elif "ålder" in cl or "alder" in cl:
            out["age"] = c
        elif "kön" in cl or "kon" in cl:
            out["sex"] = c
        elif "civilstånd" in cl or "civilstand" in cl:
            out["civil"] = c
        elif "hustyp" in cl:
            out["house_type"] = c
        elif "byggnadsperiod" in cl or "byggnadsår" in cl or "byggnadsar" in cl:
            out["period"] = c
        elif "utbildningsnivå" in cl or "utbildningsniva" in cl or "utbildning" in cl:
            out["education"] = c
        elif "näringsgren" in cl or "naringsgren" in cl:
            out["industry"] = c
        elif (
            cl in {"år", "tid", "time"}
            or cl.endswith(" år")
            or cl.startswith("år ")
            or cl.startswith("tid ")
            or cl.startswith("time ")
        ):
            # Do not classify every descriptive measure that merely contains
            # "år"/"tid" somewhere in its header as the time dimension.
            out["year"] = c

    if "year" not in out:
        # SCB CSV exports can use the actual selected year as the column name
        # when the time dimension has only one selected value.
        year_like = [
            c for c in df.columns
            if str(c).strip().isdigit() and len(str(c).strip()) == 4
        ]
        if len(year_like) == 1:
            out["year_value_column"] = year_like[0]

    return out


def value_column(df: pd.DataFrame, dims: dict[str, str]) -> str:
    dim_cols = {v for k, v in dims.items() if k != "year_value_column"}
    candidates = [c for c in df.columns if c not in dim_cols]
    # If SCB encoded the selected year as the measure column header, that is
    # exactly the numeric value column we want to read.
    if "year_value_column" in dims:
        return dims["year_value_column"]
    if not candidates:
        raise ValueError(f"No value column found. Columns: {list(df.columns)}")
    return candidates[-1]


def split_region(value: str) -> tuple[str, str]:
    s = str(value).strip()
    if " " in s and s.split(" ", 1)[0].isdigit():
        return s.split(" ", 1)[0], s.split(" ", 1)[1]
    return s[:4], s[5:] if len(s) > 5 else s


def build_panel(mig: pd.DataFrame, pop: pd.DataFrame, income: pd.DataFrame, turnout: pd.DataFrame, inequality: pd.DataFrame, housing: pd.DataFrame, completed_housing: pd.DataFrame, leisure: pd.DataFrame, crime: pd.DataFrame, labor: pd.DataFrame, education: pd.DataFrame, students: pd.DataFrame, industry: pd.DataFrame, fa15: pd.DataFrame) -> pd.DataFrame:
    md = standardize_columns(mig)
    mig = mig.copy()
    mig["value"] = normalize_number(mig["value"])
    mig["utflyttning_value"] = normalize_number(mig["utflyttning_value"])
    mig["age_num"] = mig[md["age"]].map(age_numeric)
    mig["year"] = pd.to_numeric(mig["year"], errors="coerce")
    mig[["kommun_kod", "kommun"]] = mig[md["region"]].apply(lambda x: pd.Series(split_region(x)))

    # Aggregate both sexes. Total inflow from age-specific rows.
    age_rows = mig[np.isfinite(mig["age_num"])].copy()
    mg = age_rows.groupby(["kommun_kod", "kommun", "year"], as_index=False).agg(
        inflyttade=("value", "sum"),
        utflyttade=("utflyttning_value", "sum"),
        age_weight=("age_num", lambda x: 0.0),
    )

    for lo, hi, suffix in [
        (18, 23, "18_23"),
        (24, 34, "24_34"),
        (35, 49, "35_49"),
        (63, 68, "63_68"),
        (70, 79, "70_79"),
    ]:
        part = (
            age_rows[age_rows["age_num"].between(lo, hi, inclusive="both")]
            .groupby(["kommun_kod", "kommun", "year"], as_index=False)["value"]
            .sum()
            .rename(columns={"value": f"inflyttade_{suffix}"})
        )
        mg = mg.merge(part, on=["kommun_kod", "kommun", "year"], how="left")
        mg[f"inflyttade_{suffix}"] = mg[f"inflyttade_{suffix}"].fillna(0)
    weighted = (
        age_rows.assign(wx=age_rows["value"] * age_rows["age_num"])
        .groupby(["kommun_kod", "kommun", "year"], as_index=False)
        .agg(wx=("wx", "sum"), n=("value", "sum"))
    )
    weighted["inflyttare_medelalder"] = weighted["wx"] / weighted["n"].replace(0, np.nan)
    mg = mg.drop(columns=["age_weight"]).merge(
        weighted[["kommun_kod", "kommun", "year", "inflyttare_medelalder"]],
        on=["kommun_kod", "kommun", "year"], how="left"
    )

    pdims = standardize_columns(pop)
    pop = pop.copy()
    pop["value"] = normalize_number(pop["value"])
    pop["age_num"] = pop[pdims["age"]].map(age_numeric)
    pop["year"] = pd.to_numeric(pop["year"], errors="coerce")
    pop[["kommun_kod", "kommun"]] = pop[pdims["region"]].apply(lambda x: pd.Series(split_region(x)))

    # Sexes are separate rows, so sum across sex.
    p_age = pop.groupby(["kommun_kod", "kommun", "year", pdims["age"]], as_index=False)["value"].sum()
    p_age["age_num"] = p_age[pdims["age"]].map(age_numeric)

    total = p_age[p_age["age_num"].isna()].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "folkmangd"})

    young = p_age[p_age["age_num"].between(20, 34, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_20_34"})

    pop_18_23 = p_age[p_age["age_num"].between(18, 23, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_18_23"})

    pop_24_34 = p_age[p_age["age_num"].between(24, 34, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_24_34"})

    pop_35_49 = p_age[p_age["age_num"].between(35, 49, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_35_49"})

    pop_63_68 = p_age[p_age["age_num"].between(63, 68, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_63_68"})

    pop_70_79 = p_age[p_age["age_num"].between(70, 79, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_70_79"})

    panel = mg.merge(total, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(young, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_18_23, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_24_34, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_35_49, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_63_68, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_70_79, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(
        income[["kommun_kod", "year", "inkomst_tkr"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        turnout[["kommun_kod", "year", "valdeltagande_pct", "valdeltagande_gap_pp", "valdeltagande_interpolerad"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        inequality[["kommun_kod", "year", "ekonomisk_standard_gap_pp"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        housing[[
            "kommun_kod", "year", "bostader_smahus", "bostader_totalt",
            "andel_smahus", "andel_hyresratt", "andel_bostadsratt"
        ]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        completed_housing[["kommun_kod", "year", "fardigstallda_bostader"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        leisure[["kommun_kod", "year", "fritidshus"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel["fritidshusandel_bland_smahus"] = (
        100 * panel["fritidshus"] /
        (panel["fritidshus"] + panel["bostader_smahus"]).replace(0, np.nan)
    )
    panel["kommun_nyckel"] = panel["kommun"].map(_normalize_place_name)
    panel = panel.merge(
        crime[["kommun_nyckel", "year", "brott_per_100000"]],
        on=["kommun_nyckel", "year"], how="left"
    )
    panel = panel.merge(
        labor[["kommun_kod", "year", "sysselsattningsgrad", "arbetsloshet"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        education[["kommun_kod", "year", "andel_eftergymnasial"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        students[["kommun_kod", "year", "andel_studerande"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        industry[[
            "kommun_kod", "year",
            "sysselsatta_totalt",
            "andel_industri_bc",
            "andel_hotell_restaurang_i",
            "andel_kultur_service_rstu",
        ]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        fa15[["kommun_kod", "fa15_id", "fa15_kod", "fa15_namn"]],
        on="kommun_kod", how="left"
    )

    # Functional labour-market access: jobs in the rest of the municipality's
    # FA15 region relative to the municipality's own population.
    fa_jobs = panel.groupby(["fa15_id", "year"])["sysselsatta_totalt"].transform("sum")
    panel["externa_fa_jobb"] = (fa_jobs - panel["sysselsatta_totalt"]).clip(lower=0)
    panel["externa_fa_jobb_per_1000"] = (
        1000 * panel["externa_fa_jobb"] / panel["folkmangd"].replace(0, np.nan)
    )
    panel["log_externa_fa_jobb_per_1000"] = np.log1p(panel["externa_fa_jobb_per_1000"])
    panel["andel_fa_arbetsplatser_i_egen_kommun"] = (
        100 * panel["sysselsatta_totalt"] / fa_jobs.replace(0, np.nan)
    )

    panel["andel_20_34"] = 100 * panel["bef_20_34"] / panel["folkmangd"]
    panel["bostader_per_1000"] = (
        1000 * panel["bostader_totalt"] / panel["folkmangd"].replace(0, np.nan)
    )
    panel["fardigstallda_bostader_per_1000"] = (
        1000 * panel["fardigstallda_bostader"] / panel["folkmangd"].replace(0, np.nan)
    )
    panel["inflyttning_per_1000"] = 1000 * panel["inflyttade"] / panel["folkmangd"]
    panel["utflyttning_per_1000"] = (
        1000 * panel["utflyttade"] / panel["folkmangd"].replace(0, np.nan)
    )
    panel["inflyttning_18_23_per_1000"] = (
        1000 * panel["inflyttade_18_23"] / panel["bef_18_23"].replace(0, np.nan)
    )
    panel["inflyttning_24_34_per_1000"] = (
        1000 * panel["inflyttade_24_34"] / panel["bef_24_34"].replace(0, np.nan)
    )
    panel["inflyttning_35_49_per_1000"] = (
        1000 * panel["inflyttade_35_49"] / panel["bef_35_49"].replace(0, np.nan)
    )
    panel["inflyttning_63_68_per_1000"] = (
        1000 * panel["inflyttade_63_68"] / panel["bef_63_68"].replace(0, np.nan)
    )
    panel["inflyttning_70_79_per_1000"] = (
        1000 * panel["inflyttade_70_79"] / panel["bef_70_79"].replace(0, np.nan)
    )
    panel["log_folkmangd"] = np.log(panel["folkmangd"].where(panel["folkmangd"] > 0))

    panel = panel.sort_values(["kommun_kod", "year"])
    g = panel.groupby("kommun_kod", group_keys=False)
    panel["befolkningstillvaxt_pct"] = 100 * g["folkmangd"].pct_change(fill_method=None)
    panel["bostadsbestandsforandring_pct"] = (
        100 * g["bostader_totalt"].pct_change(fill_method=None)
    )

    # All structural predictors are lagged one year so the explanatory value
    # precedes the migration outcome temporally.
    panel["lag1_inflyttning_per_1000"] = g["inflyttning_per_1000"].shift(1)
    panel["lag1_utflyttning_per_1000"] = g["utflyttning_per_1000"].shift(1)
    panel["lag1_inflyttning_18_23_per_1000"] = g["inflyttning_18_23_per_1000"].shift(1)
    panel["lag1_inflyttning_24_34_per_1000"] = g["inflyttning_24_34_per_1000"].shift(1)
    panel["lag1_inflyttning_35_49_per_1000"] = g["inflyttning_35_49_per_1000"].shift(1)
    panel["lag1_inflyttning_63_68_per_1000"] = g["inflyttning_63_68_per_1000"].shift(1)
    panel["lag1_inflyttning_70_79_per_1000"] = g["inflyttning_70_79_per_1000"].shift(1)
    panel["lag1_log_folkmangd"] = g["log_folkmangd"].shift(1)
    panel["lag1_befolkningstillvaxt_pct"] = g["befolkningstillvaxt_pct"].shift(1)
    panel["lag1_andel_20_34"] = g["andel_20_34"].shift(1)
    panel["lag1_inflyttare_medelalder"] = g["inflyttare_medelalder"].shift(1)
    panel["lag1_inkomst_tkr"] = g["inkomst_tkr"].shift(1)
    panel["lag1_valdeltagande_pct"] = g["valdeltagande_pct"].shift(1)
    panel["lag1_valdeltagande_gap_pp"] = g["valdeltagande_gap_pp"].shift(1)
    panel["lag1_ekonomisk_standard_gap_pp"] = g["ekonomisk_standard_gap_pp"].shift(1)
    panel["lag1_bostader_per_1000"] = g["bostader_per_1000"].shift(1)
    panel["lag1_bostadsbestandsforandring_pct"] = g["bostadsbestandsforandring_pct"].shift(1)
    panel["lag1_fardigstallda_bostader_per_1000"] = g["fardigstallda_bostader_per_1000"].shift(1)
    panel["lag1_andel_hyresratt"] = g["andel_hyresratt"].shift(1)
    panel["lag1_andel_bostadsratt"] = g["andel_bostadsratt"].shift(1)
    panel["lag1_andel_smahus"] = g["andel_smahus"].shift(1)
    panel["lag1_fritidshusandel_bland_smahus"] = g["fritidshusandel_bland_smahus"].shift(1)
    panel["lag1_brott_per_100000"] = g["brott_per_100000"].shift(1)
    panel["lag1_sysselsattningsgrad"] = g["sysselsattningsgrad"].shift(1)
    panel["lag1_arbetsloshet"] = g["arbetsloshet"].shift(1)
    panel["lag1_andel_eftergymnasial"] = g["andel_eftergymnasial"].shift(1)
    panel["lag1_andel_studerande"] = g["andel_studerande"].shift(1)
    panel["lag1_andel_industri_bc"] = g["andel_industri_bc"].shift(1)
    panel["lag1_andel_hotell_restaurang_i"] = g["andel_hotell_restaurang_i"].shift(1)
    panel["lag1_andel_kultur_service_rstu"] = g["andel_kultur_service_rstu"].shift(1)
    panel["lag1_log_externa_fa_jobb_per_1000"] = g["log_externa_fa_jobb_per_1000"].shift(1)
    panel["lag1_andel_fa_arbetsplatser_i_egen_kommun"] = g["andel_fa_arbetsplatser_i_egen_kommun"].shift(1)

    return panel.reset_index(drop=True)


def metrics(y_true, y_pred) -> dict:
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def _finite_float(value):
    try:
        value = float(value)
    except Exception:
        return None
    return value if np.isfinite(value) else None


def _metrics(y_true, y_pred) -> dict:
    return {
        "r2": _finite_float(r2_score(y_true, y_pred)),
        "rmse": _finite_float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": _finite_float(mean_absolute_error(y_true, y_pred)),
    }


def _design_with_year_effects(d: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    year_dummies = pd.get_dummies(
        d["year"].astype(int).astype(str),
        prefix="year",
        drop_first=True,
        dtype=float,
    )
    X = pd.concat(
        [d[features].reset_index(drop=True), year_dummies.reset_index(drop=True)],
        axis=1,
    )
    return sm.add_constant(X, has_constant="add").astype(float)


def _backward_aic_selection(
    d: pd.DataFrame,
    features: list[str],
    target: str,
    min_improvement: float = 2.0,
) -> tuple[list[str], list[dict]]:
    """Backward elimination by AIC; year fixed effects are always retained."""
    selected = list(features)
    history = []

    def fit_aic(fs: list[str]) -> float:
        X = _design_with_year_effects(d, fs)
        y = d[target].astype(float).reset_index(drop=True)
        return float(sm.OLS(y, X).fit().aic)

    current_aic = fit_aic(selected)
    while len(selected) > 1:
        candidates = []
        for feature in selected:
            trial = [f for f in selected if f != feature]
            aic = fit_aic(trial)
            candidates.append((aic, feature, trial))
        best_aic, removed, trial = min(candidates, key=lambda x: x[0])
        improvement = current_aic - best_aic
        if improvement < min_improvement:
            break
        history.append({
            "removed": removed,
            "aic_before": _finite_float(current_aic),
            "aic_after": _finite_float(best_aic),
            "improvement": _finite_float(improvement),
        })
        selected = trial
        current_aic = best_aic

    return selected, history


def _elastic_net_selection(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> tuple[list[str], dict]:
    """
    Elastic Net variable selection on within-year deviations.
    Demeaning by year keeps the selector focused on municipal differences
    while year fixed effects remain unpenalized in the final OLS model.
    """
    work = d[["year", target] + features].dropna().reset_index(drop=True)
    if len(work) < max(30, len(features) * 5):
        return list(features), {"reason": "too_few_observations"}

    X = work[features].astype(float)
    y = work[target].astype(float)
    Xw = X - X.groupby(work["year"]).transform("mean")
    yw = y - y.groupby(work["year"]).transform("mean")

    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xw)

    years = sorted(work["year"].unique())
    if len(years) >= 3:
        splits = []
        for yr in years:
            test_idx = np.flatnonzero(work["year"].to_numpy() == yr)
            train_idx = np.flatnonzero(work["year"].to_numpy() != yr)
            if len(test_idx) and len(train_idx):
                splits.append((train_idx, test_idx))
        cv = splits
    else:
        cv = min(5, max(2, len(work) // 30))

    model = ElasticNetCV(
        l1_ratio=[0.1, 0.5, 0.9, 1.0],
        alphas=np.logspace(-4, 2, 80),
        cv=cv,
        max_iter=50000,
        random_state=42,
    ).fit(Xs, yw)

    coefs = np.asarray(model.coef_)
    selected = [f for f, c in zip(features, coefs) if abs(float(c)) > 1e-8]
    if not selected:
        selected = [features[int(np.argmax(np.abs(coefs)))]]

    return selected, {
        "alpha": _finite_float(model.alpha_),
        "l1_ratio": _finite_float(model.l1_ratio_),
        "coefficients": [
            {"feature": f, "penalized_coefficient": _finite_float(c)}
            for f, c in zip(features, coefs)
        ],
    }


FEATURE_THEMES = {
    "lag1_inflyttning_per_1000": "Historisk inflyttningsdynamik",
    "lag1_utflyttning_per_1000": "Historisk utflyttningsdynamik",
    "lag1_inflyttning_18_23_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_24_34_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_35_49_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_63_68_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_70_79_per_1000": "Historisk flyttdynamik",
    "lag1_log_folkmangd": "Kommunstorlek",
    "lag1_befolkningstillvaxt_pct": "Befolkningsdynamik",
    "lag1_andel_20_34": "Åldersstruktur",
    "lag1_inflyttare_medelalder": "Inflyttarprofil",
    "lag1_inkomst_tkr": "Inkomstnivå",
    "lag1_valdeltagande_pct": "Demokratisk delaktighet",
    "lag1_valdeltagande_gap_pp": "Demokratisk ojämlikhet",
    "lag1_ekonomisk_standard_gap_pp": "Socioekonomiska klyftor",
    "lag1_bostader_per_1000": "Bostadsutbud",
    "lag1_bostadsbestandsforandring_pct": "Bostadsdynamik",
    "lag1_fardigstallda_bostader_per_1000": "Bostadsdynamik",
    "lag1_andel_hyresratt": "Upplåtelseform",
    "lag1_andel_bostadsratt": "Upplåtelseform",
    "lag1_andel_smahus": "Landets lugn",
    "lag1_fritidshusandel_bland_smahus": "Landets lugn",
    "lag1_brott_per_100000": "Landets lugn",
    "lag1_sysselsattningsgrad": "Arbetsmarknad",
    "lag1_arbetsloshet": "Arbetsmarknad",
    "lag1_andel_eftergymnasial": "Humankapital",
    "lag1_andel_studerande": "Studentmiljö",
    "lag1_andel_industri_bc": "Näringslivsprofil",
    "lag1_andel_hotell_restaurang_i": "Näringslivsprofil",
    "lag1_andel_kultur_service_rstu": "Näringslivsprofil",
    "lag1_log_externa_fa_jobb_per_1000": "Regional arbetsmarknadsaccess",
    "lag1_andel_fa_arbetsplatser_i_egen_kommun": "Regional arbetsmotor",
}


def _thematic_selection(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> tuple[list[str], dict]:
    """
    Keep qualitatively distinct explanatory perspectives.
    If several variables represent the same theme, keep the one with the
    strongest incremental AIC contribution in the current model.
    """
    if not features:
        return [], {"themes": {}, "incremental_aic": []}

    def fit_aic(fs: list[str]) -> float:
        X = _design_with_year_effects(d, fs)
        y = d[target].astype(float).reset_index(drop=True)
        return float(sm.OLS(y, X).fit().aic)

    full_aic = fit_aic(features)
    contributions = []
    for feature in features:
        trial = [f for f in features if f != feature]
        if not trial:
            delta = float("inf")
        else:
            delta = fit_aic(trial) - full_aic
        contributions.append({
            "feature": feature,
            "theme": FEATURE_THEMES.get(feature, feature),
            "delta_aic_when_removed": _finite_float(delta),
        })

    by_theme = {}
    for row in contributions:
        by_theme.setdefault(row["theme"], []).append(row)

    selected = []
    theme_choice = {}
    for theme, rows in by_theme.items():
        best = max(
            rows,
            key=lambda r: -1e18 if r["delta_aic_when_removed"] is None else r["delta_aic_when_removed"],
        )
        # Because backward-AIC has already screened the candidate set, unique
        # themes remain eligible; duplicate themes compete for one slot.
        selected.append(best["feature"])
        theme_choice[theme] = best["feature"]

    selected = [f for f in features if f in selected]
    return selected, {
        "themes": theme_choice,
        "incremental_aic": contributions,
        "n_themes": len(theme_choice),
        "rule": "max one variable per qualitative theme; within-theme choice by incremental AIC",
    }


def _temporal_cv_rmse(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> list[float]:
    """
    Rolling-origin validation by year. Each validation year is predicted only
    from earlier years, so the score measures temporal generalization.
    """
    work = d[["year", target] + features].dropna().copy()
    years = sorted(int(y) for y in work["year"].unique())
    if len(years) < 4:
        return []

    scores = []
    for valid_year in years[2:]:
        train = work[work["year"] < valid_year]
        valid = work[work["year"] == valid_year]
        if len(train) < max(30, len(features) * 5) or len(valid) == 0:
            continue

        model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
        model.fit(train[features], train[target])
        pred = model.predict(valid[features])
        scores.append(float(np.sqrt(mean_squared_error(valid[target], pred))))

    return scores


def _temporal_cv_selection(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> tuple[list[str], dict]:
    """
    Backward pruning using rolling-origin RMSE and the one-standard-error rule.
    A variable is removed when the simpler model performs within one standard
    error of the current model. This favors parsimony without requiring a
    tiny in-sample improvement to justify extra predictors.
    """
    selected = list(features)
    history = []

    current_scores = _temporal_cv_rmse(d, selected, target)
    if len(current_scores) < 3:
        return selected, {
            "reason": "fewer_than_3_temporal_folds",
            "folds": len(current_scores),
            "selected": selected,
            "history": history,
        }

    while len(selected) > 2:
        current_mean = float(np.mean(current_scores))
        current_se = float(np.std(current_scores, ddof=1) / np.sqrt(len(current_scores)))

        candidates = []
        for feature in selected:
            trial = [f for f in selected if f != feature]
            scores = _temporal_cv_rmse(d, trial, target)
            if len(scores) != len(current_scores) or not scores:
                continue
            candidates.append((
                float(np.mean(scores)),
                feature,
                trial,
                scores,
            ))

        if not candidates:
            break

        best_mean, removed, trial, best_scores = min(candidates, key=lambda x: x[0])

        # One-standard-error rule: prefer the simpler model if its temporal
        # RMSE is not materially worse than the current model.
        if best_mean <= current_mean + current_se:
            history.append({
                "removed": removed,
                "rmse_before": _finite_float(current_mean),
                "rmse_after": _finite_float(best_mean),
                "se_before": _finite_float(current_se),
                "folds": len(current_scores),
            })
            selected = trial
            current_scores = best_scores
        else:
            break

    return selected, {
        "folds": len(current_scores),
        "mean_rmse": _finite_float(float(np.mean(current_scores))) if current_scores else None,
        "selected": selected,
        "history": history,
        "rule": "rolling-origin RMSE, one-standard-error rule",
    }


def _select_features(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> dict:
    elastic, elastic_meta = _elastic_net_selection(d, features, target)
    backward, backward_history = _backward_aic_selection(d, features, target)

    consensus = [f for f in features if f in elastic and f in backward]
    if len(consensus) < 2:
        consensus = list(backward)
    if not consensus:
        consensus = [features[0]]

    thematic, thematic_meta = _thematic_selection(d, consensus, target)
    if not thematic:
        thematic = consensus

    temporal, temporal_meta = _temporal_cv_selection(d, thematic, target)
    # CV is allowed to prune only when at least three genuine temporal folds
    # exist. Otherwise keep the theme-balanced model rather than over-pruning.
    if temporal_meta.get("folds", 0) >= 3:
        selected = temporal
    else:
        selected = thematic

    excluded = [f for f in features if f not in selected]
    return {
        "selected": selected,
        "excluded": excluded,
        "elastic_net_selected": elastic,
        "backward_aic_selected": backward,
        "pre_theme_consensus": consensus,
        "thematic_selected": thematic,
        "temporal_cv_selected": temporal,
        "elastic_net": elastic_meta,
        "backward_aic_history": backward_history,
        "thematic_selection": thematic_meta,
        "temporal_cv": temporal_meta,
    }


def _pairwise_variable_matrix(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> dict:
    """
    Pairwise diagnostics for the selected analysis window.
    For each pair: Pearson correlation, joint adjusted R2 with year effects,
    and incremental adjusted R2 over the stronger single-variable model.
    """
    rows = []
    single_adj = {}

    for feature in features:
        work = d[["year", target, feature]].dropna().reset_index(drop=True)
        X = _design_with_year_effects(work, [feature])
        y = work[target].astype(float).reset_index(drop=True)
        fit = sm.OLS(y, X).fit()
        single_adj[feature] = float(fit.rsquared_adj)

    for i, x in enumerate(features):
        for j, yvar in enumerate(features):
            if j < i:
                continue

            cols = ["year", target, x] if x == yvar else ["year", target, x, yvar]
            work = d[cols].dropna().reset_index(drop=True)

            if x == yvar:
                corr = 1.0
                joint_adj = single_adj[x]
                incremental = 0.0
            else:
                corr = float(work[[x, yvar]].corr().iloc[0, 1])
                X = _design_with_year_effects(work, [x, yvar])
                yy = work[target].astype(float).reset_index(drop=True)
                fit = sm.OLS(yy, X).fit()
                joint_adj = float(fit.rsquared_adj)
                incremental = joint_adj - max(single_adj[x], single_adj[yvar])

            rows.append({
                "x": x,
                "y": yvar,
                "correlation": _finite_float(corr),
                "joint_adjusted_r2": _finite_float(joint_adj),
                "incremental_adjusted_r2": _finite_float(incremental),
                "x_theme": FEATURE_THEMES.get(x, x),
                "y_theme": FEATURE_THEMES.get(yvar, yvar),
                "same_theme": FEATURE_THEMES.get(x, x) == FEATURE_THEMES.get(yvar, yvar),
                "n_obs": int(len(work)),
            })

    return {
        "features": list(features),
        "single_adjusted_r2": {
            f: _finite_float(v) for f, v in single_adj.items()
        },
        "rows": rows,
    }


def _theme_marginal_analysis(
    d: pd.DataFrame,
    selected_features: list[str],
    target: str,
) -> dict:
    """
    Leave-one-theme-out contribution analysis on the same explanation sample.
    Positive deltas mean the full model performs better than the model without
    that theme.
    """
    if not selected_features:
        return {"rows": [], "full_model_rmse": None}

    y = d[target].reset_index(drop=True).astype(float)
    X_full = _design_with_year_effects(d, selected_features)
    full_fit = sm.OLS(y, X_full).fit()
    full_rmse = float(np.sqrt(np.mean(np.square(full_fit.resid))))

    theme_to_features: dict[str, list[str]] = {}
    for feature in selected_features:
        theme = FEATURE_THEMES.get(feature, feature)
        theme_to_features.setdefault(theme, []).append(feature)

    rows = []
    for theme, theme_features in theme_to_features.items():
        reduced_features = [f for f in selected_features if f not in theme_features]
        X_reduced = _design_with_year_effects(d, reduced_features)
        reduced_fit = sm.OLS(y, X_reduced).fit()
        reduced_rmse = float(np.sqrt(np.mean(np.square(reduced_fit.resid))))

        rows.append({
            "theme": theme,
            "features": theme_features,
            "full_adjusted_r2": _finite_float(full_fit.rsquared_adj),
            "reduced_adjusted_r2": _finite_float(reduced_fit.rsquared_adj),
            "delta_adjusted_r2": _finite_float(full_fit.rsquared_adj - reduced_fit.rsquared_adj),
            "full_aic": _finite_float(full_fit.aic),
            "reduced_aic": _finite_float(reduced_fit.aic),
            "delta_aic": _finite_float(reduced_fit.aic - full_fit.aic),
            "full_rmse": _finite_float(full_rmse),
            "reduced_rmse": _finite_float(reduced_rmse),
            "delta_rmse": _finite_float(reduced_rmse - full_rmse),
        })

    rows.sort(key=lambda r: (r["delta_adjusted_r2"] if r["delta_adjusted_r2"] is not None else -1e9), reverse=True)
    return {
        "rule": "remove one qualitative theme at a time from the selected full model",
        "full_model_rmse": _finite_float(full_rmse),
        "rows": rows,
    }


def _explanation_model(df: pd.DataFrame, features: list[str], target: str, window: int) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    latest_year = int(df["year"].max())
    start_year = latest_year - window + 1
    d = df[df["year"].between(start_year, latest_year)].copy()
    selection = _select_features(d, features, target)
    selected_features = selection["selected"]

    # Year fixed effects absorb common national shocks/trends within the pooled window.
    X = _design_with_year_effects(d, selected_features)
    y = d[target].reset_index(drop=True).astype(float)
    groups = d["kommun_kod"].reset_index(drop=True)

    base_fit = sm.OLS(y, X).fit()
    robust_fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups})

    names = list(robust_fit.model.exog_names)
    params = np.asarray(robust_fit.params)
    pvals = np.asarray(robust_fit.pvalues)
    conf = np.asarray(robust_fit.conf_int())

    y_sd = float(np.nanstd(y, ddof=1))
    coeffs = []
    for feature in selected_features:
        i = names.index(feature)
        x_sd = float(np.nanstd(d[feature], ddof=1))
        beta_std = params[i] * x_sd / y_sd if y_sd > 0 and x_sd > 0 else np.nan
        coeffs.append({
            "feature": feature,
            "coefficient": _finite_float(params[i]),
            "standardized_coefficient": _finite_float(beta_std),
            "p_value": _finite_float(pvals[i]),
            "ci_low": _finite_float(conf[i, 0]),
            "ci_high": _finite_float(conf[i, 1]),
        })

    vif_rows = []
    vif_X = sm.add_constant(d[selected_features].astype(float), has_constant="add")
    for i, feature in enumerate(selected_features, start=1):
        try:
            vif = variance_inflation_factor(vif_X.to_numpy(), i)
        except Exception:
            vif = np.nan
        vif_rows.append({"feature": feature, "vif": _finite_float(vif)})

    influence = base_fit.get_influence()
    fitted = np.asarray(base_fit.fittedvalues)
    resid = np.asarray(base_fit.resid)
    std_resid = np.asarray(influence.resid_studentized_internal)
    cooks = np.asarray(influence.cooks_distance[0])

    diag = d[["kommun_kod", "kommun", "year"]].reset_index(drop=True).copy()
    diag["window"] = window
    diag["fitted"] = fitted
    diag["residual"] = resid
    diag["std_residual"] = std_resid
    diag["cooks_distance"] = cooks

    sorted_resid = np.sort(std_resid[np.isfinite(std_resid)])
    n = len(sorted_resid)
    probs = (np.arange(1, n + 1) - 0.5) / n if n else np.array([])
    qq = pd.DataFrame({
        "window": window,
        "theoretical": norm.ppf(probs) if n else [],
        "sample": sorted_resid,
    })

    intercept = _finite_float(params[names.index("const")]) if "const" in names else None
    year_effects = []
    for name, value in zip(names, params):
        if str(name).startswith("year_"):
            year_effects.append({
                "year": str(name).replace("year_", "", 1),
                "coefficient": _finite_float(value),
            })

    result = {
        "window": window,
        "start_year": start_year,
        "end_year": latest_year,
        "n_obs": int(len(d)),
        "n_municipalities": int(d["kommun_kod"].nunique()),
        "r2": _finite_float(base_fit.rsquared),
        "adjusted_r2": _finite_float(base_fit.rsquared_adj),
        "aic": _finite_float(base_fit.aic),
        "bic": _finite_float(base_fit.bic),
        "coefficients": coeffs,
        "intercept": intercept,
        "year_effect_coefficients": year_effects,
        "equation_note": "Mål = intercept + summan av koefficient × variabel + årseffekter",
        "vif": vif_rows,
        "variable_selection": selection,
        "selected_features": selected_features,
        "excluded_features": selection["excluded"],
        "pairwise_matrix": _pairwise_variable_matrix(d, features, target),
        "theme_marginal_analysis": _theme_marginal_analysis(d, selected_features, target),
        "standard_errors": "Klustrade per kommun",
        "year_fixed_effects": True,
    }
    return result, diag, qq


def fit_models(panel: pd.DataFrame) -> dict:
    target = "inflyttning_per_1000"
    features = [
        "lag1_inflyttning_per_1000",
        "lag1_utflyttning_per_1000",
        "lag1_log_folkmangd",
        "lag1_befolkningstillvaxt_pct",
        "lag1_andel_20_34",
        "lag1_inflyttare_medelalder",
        "lag1_inkomst_tkr",
        "lag1_valdeltagande_pct",
        "lag1_valdeltagande_gap_pp",
        "lag1_ekonomisk_standard_gap_pp",
        "lag1_bostader_per_1000",
        "lag1_bostadsbestandsforandring_pct",
        "lag1_fardigstallda_bostader_per_1000",
        "lag1_andel_hyresratt",
        "lag1_andel_bostadsratt",
        "lag1_andel_smahus",
        "lag1_fritidshusandel_bland_smahus",
        "lag1_brott_per_100000",
        "lag1_sysselsattningsgrad",
        "lag1_arbetsloshet",
        "lag1_andel_eftergymnasial",
        "lag1_andel_studerande",
        "lag1_andel_industri_bc",
        "lag1_andel_hotell_restaurang_i",
        "lag1_andel_kultur_service_rstu",
        "lag1_log_externa_fa_jobb_per_1000",
        "lag1_andel_fa_arbetsplatser_i_egen_kommun",
    ]
    model_df = panel.dropna(subset=[target] + features).copy()
    test_year = int(model_df["year"].max())

    windows = {}
    pred_frames = []
    diag_frames = []
    qq_frames = []

    for window in range(1, 6):
        explanation, diag, qq = _explanation_model(model_df, features, target, window)
        diag_frames.append(diag)
        qq_frames.append(qq)

        train_start = test_year - window
        train = model_df[model_df["year"].between(train_start, test_year - 1)].copy()
        test = model_df[model_df["year"] == test_year].copy()

        validation_candidates = [f for f in features if f not in LOOKAHEAD_ONLY_FEATURES]
        validation_selection = _select_features(train, validation_candidates, target)
        validation_features = validation_selection["selected"]

        Xtr, ytr = train[validation_features], train[target]
        Xte, yte = test[validation_features], test[target]

        naive_pred = test["lag1_inflyttning_per_1000"].to_numpy()
        naive = _metrics(yte, naive_pred)

        ols = LinearRegression().fit(Xtr, ytr)
        ols_pred = ols.predict(Xte)
        ols_m = _metrics(yte, ols_pred)

        ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25))).fit(Xtr, ytr)
        ridge_pred = ridge.predict(Xte)
        ridge_m = _metrics(yte, ridge_pred)

        pred = test[["kommun_kod", "kommun", "year", target]].copy()
        pred["window"] = window
        pred["pred_naiv"] = naive_pred
        pred["pred_ols"] = ols_pred
        pred["pred_ridge"] = ridge_pred
        pred_frames.append(pred)

        windows[str(window)] = {
            "explanation": explanation,
            "validation": {
                "train_start_year": train_start,
                "train_end_year": test_year - 1,
                "test_year": test_year,
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "selected_features": validation_features,
                "excluded_features": validation_selection["excluded"],
                "variable_selection": validation_selection,
                "models": {
                    "naive": naive,
                    "ols": ols_m,
                    "ridge": ridge_m,
                },
            },
        }

    pd.concat(pred_frames, ignore_index=True).to_csv(OUT / "predictions.csv", index=False)
    pd.concat(diag_frames, ignore_index=True).to_csv(OUT / "diagnostics.csv", index=False)
    pd.concat(qq_frames, ignore_index=True).to_csv(OUT / "qq.csv", index=False)

    return {
        "generated_from_year": START_YEAR,
        "generated_to_year": END_YEAR,
        "test_year": test_year,
        "default_window": 5,
        "max_window": 5,
        "target": target,
        "features": features,
        "windows": windows,
        "notes": [
            "Förklaringsmodellen använder kommun-år och som standard de fem senaste observerade åren.",
            "Årseffekter ingår i förklaringsmodellen för att fånga gemensamma nationella årsvariationer.",
            "Standardfel i förklaringsmodellen är klustrade per kommun eftersom samma kommun förekommer flera år.",
            "Prognosvalideringen för teståret använder endast de föregående 1–5 åren beroende på valt analysfönster.",
            "Föregående års utflyttning per 1 000 invånare testas som ett separat historiskt dynamiktema för att se om utflödet tillför information utöver föregående års inflyttning.",
            "Inkomst avser genomsnittlig sammanräknad förvärvsinkomst för 20–64-åringar och används laggad ett år.",
            "Landets lugn testas som ett gemensamt tema där andel småhus, anmälda brott per 100 000 invånare och fritidshusandel bland småhusliknande bostäder konkurrerar om att representera temat.",
            "Bostadsutbud mäts som totalt bostadsbestånd per 1 000 invånare enligt SCB BO0104T04 och används laggat ett år.",
            "Bostadsdynamik testas med både årlig förändring i bostadsbeståndet och färdigställda lägenheter i nybyggda hus per 1 000 invånare; högst en av dessa behålls inom temat.",
            "Upplåtelseform testas med andel hyresrätt respektive bostadsrätt av bostadsbeståndet; högst en representant behålls inom temat.",
            "Andel småhus avser lägenheter i småhus dividerat med samtliga lägenheter i småhus, flerbostadshus, övriga hus och specialbostäder enligt SCB BO0104T04 och används laggad ett år.",
            "Fritidshusandelen beräknas som fritidshus / (fritidshus + bostäder i småhus) enligt SCB BO0104T08 och BO0104T04; måttet är en proxy eftersom fritidshus räknas som hus medan småhuskomponenten räknas som bostadslägenheter.",
            "Brottsmåttet är totalt antal anmälda brott per 100 000 invånare från BRÅ:s årsvisa kommunstatistik i Lulea-statistik/BR-brottsstatistik och används laggat ett år.",
            "Arbetsmarknadsvariablerna är sysselsättningsgrad och arbetslöshet bland 20–64-åringar från SCB BAS och används laggade ett år.",
            "Utbildningsvariabeln är andel 25–64-åringar med eftergymnasial utbildning och används laggad ett år.",
            "Studentmiljö mäts som andel studerande bland 20–64-åringar enligt SCB IntGr8Kom1N och används laggad ett år.",
            "Näringslivsprofilen testas med andel sysselsatta efter arbetsställets belägenhet i B+C industri/gruvor, I hotell/restaurang samt R+S+T+U kultur/nöje/service enligt SCB ArRegUtb; högst en representant behålls från temat.",
            "Regional arbetsmarknadsaccess mäts som log(1 + jobb i övriga kommuner inom samma FA15-region per 1 000 invånare i den egna kommunen), laggad ett år.",
            "Regional arbetsmotor mäts som den egna kommunens arbetsplatser dividerat med samtliga arbetsplatser inom samma FA15-region, uttryckt i procent och laggat ett år.",
            "Variabelurvalet kombinerar Elastic Net, backward-AIC, tematisk diversifiering och tidsbaserad rolling-origin-korsvalidering.",
            "När flera variabler beskriver samma kvalitativa tema behålls högst en representant, vald efter inkrementellt AIC-bidrag.",
            "Tidsbaserad CV får endast sålla variabler när minst tre giltiga rolling-origin-foldar finns; annars behålls den tematiskt balanserade modellen.",
            "Alla strukturella förklaringsvariabler används laggade ett år för tydligare tidsordning mot inflyttningen.",
            "Variabelmatrisen redovisar parvis korrelation, gemensamt justerat R² samt extra justerat R² jämfört med den starkaste variabeln ensam.",
            "Tematisk marginalanalys tar bort ett valt tema i taget från fullmodellen och visar förändringen i justerat R², AIC och RMSE på samma analysurval.",
            "Separata livsfasmodeller skattas för 18–23, 24–34, 35–49, 63–68 och 70–79 år, med inflyttade per 1 000 invånare i samma åldersgrupp som mål och åldersgruppens egen föregående inflyttning som historisk dynamik.",
            "Om konsensusurvalet blir alltför litet används backward-AIC som reserv för att undvika instabila små modeller.",
            "Urvalet för prognosvalidering görs endast på träningsåren och får inte se teståret.",
            "Valdeltagande och valdeltagandeklyfta bygger på riksdagsvalen 2018, 2022 och 2026 och linjär interpolation mellan valåren. De används i den förklarande analysen men utesluts från prognosvalideringen eftersom interpolation mot ett senare val annars skulle ge framtidsinformation.",
            "Valdeltagandeklyfta mäts som högsta minus lägsta valdeltagande mellan valdistrikt inom kommunen, i procentenheter. Valdistrikt är valgeografi och ska inte förväxlas med DeSO.",
            "Socioekonomisk klyfta mäts som högsta minus lägsta andel med låg ekonomisk standard mellan kommunens DeSO, i procentenheter. SCB byter DeSO-version för 2024, vilket dokumenteras som ett möjligt nivåbrott.",
            "Samband ska inte tolkas som säkra kausala effekter; endogenitet och utelämnade variabler kan finnas.",
        ],
    }



def fit_age_group_models(panel: pd.DataFrame) -> dict:
    """
    Separate five-year explanatory/validation models for selected life-stage
    age groups. Outcomes are in-migrants per 1,000 residents in the same
    age group, which avoids mechanically rewarding municipalities simply
    because they have a larger share of that age group.
    """
    structural_features = [
        "lag1_utflyttning_per_1000",
        "lag1_log_folkmangd",
        "lag1_befolkningstillvaxt_pct",
        "lag1_andel_20_34",
        "lag1_inflyttare_medelalder",
        "lag1_inkomst_tkr",
        "lag1_valdeltagande_pct",
        "lag1_valdeltagande_gap_pp",
        "lag1_ekonomisk_standard_gap_pp",
        "lag1_bostader_per_1000",
        "lag1_bostadsbestandsforandring_pct",
        "lag1_fardigstallda_bostader_per_1000",
        "lag1_andel_hyresratt",
        "lag1_andel_bostadsratt",
        "lag1_andel_smahus",
        "lag1_fritidshusandel_bland_smahus",
        "lag1_brott_per_100000",
        "lag1_sysselsattningsgrad",
        "lag1_arbetsloshet",
        "lag1_andel_eftergymnasial",
        "lag1_andel_studerande",
        "lag1_andel_industri_bc",
        "lag1_andel_hotell_restaurang_i",
        "lag1_andel_kultur_service_rstu",
        "lag1_log_externa_fa_jobb_per_1000",
        "lag1_andel_fa_arbetsplatser_i_egen_kommun",
    ]

    specs = {
        "18_23": {
            "label": "18–23 år",
            "interpretation": "Student-/etableringsålder",
            "target": "inflyttning_18_23_per_1000",
            "lag_target": "lag1_inflyttning_18_23_per_1000",
        },
        "24_34": {
            "label": "24–34 år",
            "interpretation": "Etablering i arbetsliv och familjebildning",
            "target": "inflyttning_24_34_per_1000",
            "lag_target": "lag1_inflyttning_24_34_per_1000",
        },
        "35_49": {
            "label": "35–49 år",
            "interpretation": "Familje-/yrkesetablering",
            "target": "inflyttning_35_49_per_1000",
            "lag_target": "lag1_inflyttning_35_49_per_1000",
        },
        "63_68": {
            "label": "63–68 år",
            "interpretation": "Pensionsnära/pensionsövergång",
            "target": "inflyttning_63_68_per_1000",
            "lag_target": "lag1_inflyttning_63_68_per_1000",
        },
        "70_79": {
            "label": "70–79 år",
            "interpretation": "Senare pensionsfas",
            "target": "inflyttning_70_79_per_1000",
            "lag_target": "lag1_inflyttning_70_79_per_1000",
        },
    }

    out = {}
    for key, spec in specs.items():
        features = [spec["lag_target"]] + structural_features
        d = panel.dropna(subset=[spec["target"]] + features).copy()
        if d.empty:
            out[key] = {**spec, "error": "Inga kompletta observationer"}
            continue

        test_year = int(d["year"].max())
        explanation, _, _ = _explanation_model(d, features, spec["target"], 5)

        train = d[d["year"].between(test_year - 5, test_year - 1)].copy()
        test = d[d["year"] == test_year].copy()
        validation = None

        if not train.empty and not test.empty:
            validation_candidates = [f for f in features if f not in LOOKAHEAD_ONLY_FEATURES]
            sel = _select_features(train, validation_candidates, spec["target"])
            vf = sel["selected"]
            Xtr, ytr = train[vf], train[spec["target"]]
            Xte, yte = test[vf], test[spec["target"]]

            naive_pred = test[spec["lag_target"]].to_numpy()
            ols = LinearRegression().fit(Xtr, ytr)
            ridge = make_pipeline(
                StandardScaler(),
                RidgeCV(alphas=np.logspace(-3, 3, 25))
            ).fit(Xtr, ytr)

            validation = {
                "test_year": test_year,
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "selected_features": vf,
                "models": {
                    "naive": _metrics(yte, naive_pred),
                    "ols": _metrics(yte, ols.predict(Xte)),
                    "ridge": _metrics(yte, ridge.predict(Xte)),
                },
            }

        out[key] = {
            **spec,
            "rate_definition": "Inflyttade i åldersgruppen per 1 000 invånare i samma åldersgrupp",
            "explanation": explanation,
            "validation": validation,
        }

    return out

def main():
    if "--preflight-only" in sys.argv:
        preflight_sources()
        return

    # Manual runs keep the safety check by default. GitHub Actions uses
    # --skip-preflight after its separate preflight step has already succeeded.
    if "--skip-preflight" not in sys.argv:
        preflight_sources()

    # Fetch the newly added smaller sources first so schema errors fail early.
    turnout = get_turnout_series()
    inequality = get_socioeconomic_gap()

    labor = get_labor_market()
    education = get_education()
    students = get_students()
    industry = get_industry_structure()
    fa15 = get_fa15_membership()
    mig = get_migration()
    pop = get_population()
    income = get_income()
    housing = get_housing()
    completed_housing = get_completed_housing()
    leisure = get_leisure_houses()
    crime = get_crime_total()
    panel = build_panel(mig, pop, income, turnout, inequality, housing, completed_housing, leisure, crime, labor, education, students, industry, fa15)
    panel.to_csv(OUT / "panel.csv", index=False)
    result = fit_models(panel)
    result["age_group_models"] = fit_age_group_models(panel)
    (OUT / "model.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
