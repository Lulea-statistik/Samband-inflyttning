#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
import re
import time
from pathlib import Path

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
HOUSING_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
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
    r = session.get(url, timeout=60)
    if not r.ok:
        raise RuntimeError(f"SCB metadata failed {r.status_code} for {url}: {r.text[:500]}")
    return r.json()


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
            content["code"]: [inflow_code],
            time["code"]: [str(year)],
        })
        dims = standardize_columns(df)
        value_candidates = [c for c in df.columns if c not in set(dims.values())]
        if len(value_candidates) != 1:
            raise ValueError(f"Expected one migration value column for {year}, got {value_candidates}")
        df = df.rename(columns={value_candidates[0]: "value"})
        df["year"] = year
        rows.append(df)
        print(f"Migration {year}: {len(df):,} rows")
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
            (np.isfinite(a) and (18 <= a <= 34 or 63 <= a <= 68))
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
        df["_is_small"] = df[hcol].astype(str).str.lower().str.contains(
            "småhus", regex=False
        )

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

        agg = totals.merge(
            small,
            on=["kommun_kod", "kommun", "year"],
            how="left",
        )
        agg["andel_smahus"] = (
            100 * agg["bostader_smahus"] / agg["bostader_totalt"].replace(0, np.nan)
        )
        rows.append(agg[[
            "kommun_kod", "kommun", "year",
            "bostader_smahus", "bostader_totalt", "andel_smahus"
        ]])
        print(f"Housing {year}: {len(agg):,} municipalities")

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
            or "år" in cl
            or "tid" in cl
        ):
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


def build_panel(mig: pd.DataFrame, pop: pd.DataFrame, income: pd.DataFrame, housing: pd.DataFrame, labor: pd.DataFrame, education: pd.DataFrame, students: pd.DataFrame, industry: pd.DataFrame, fa15: pd.DataFrame) -> pd.DataFrame:
    md = standardize_columns(mig)
    mig = mig.copy()
    mig["value"] = normalize_number(mig["value"])
    mig["age_num"] = mig[md["age"]].map(age_numeric)
    mig["year"] = pd.to_numeric(mig["year"], errors="coerce")
    mig[["kommun_kod", "kommun"]] = mig[md["region"]].apply(lambda x: pd.Series(split_region(x)))

    # Aggregate both sexes. Total inflow from age-specific rows.
    age_rows = mig[np.isfinite(mig["age_num"])].copy()
    mg = age_rows.groupby(["kommun_kod", "kommun", "year"], as_index=False).agg(
        inflyttade=("value", "sum"),
        age_weight=("age_num", lambda x: 0.0),
    )

    for lo, hi, suffix in [(18, 23, "18_23"), (63, 68, "63_68")]:
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

    pop_63_68 = p_age[p_age["age_num"].between(63, 68, inclusive="both")].groupby(
        ["kommun_kod", "kommun", "year"], as_index=False
    )["value"].sum().rename(columns={"value": "bef_63_68"})

    panel = mg.merge(total, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(young, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_18_23, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(pop_63_68, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(
        income[["kommun_kod", "year", "inkomst_tkr"]],
        on=["kommun_kod", "year"], how="left"
    )
    panel = panel.merge(
        housing[["kommun_kod", "year", "andel_smahus"]],
        on=["kommun_kod", "year"], how="left"
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

    panel["andel_20_34"] = 100 * panel["bef_20_34"] / panel["folkmangd"]
    panel["inflyttning_per_1000"] = 1000 * panel["inflyttade"] / panel["folkmangd"]
    panel["inflyttning_18_23_per_1000"] = (
        1000 * panel["inflyttade_18_23"] / panel["bef_18_23"].replace(0, np.nan)
    )
    panel["inflyttning_63_68_per_1000"] = (
        1000 * panel["inflyttade_63_68"] / panel["bef_63_68"].replace(0, np.nan)
    )
    panel["log_folkmangd"] = np.log(panel["folkmangd"].where(panel["folkmangd"] > 0))

    panel = panel.sort_values(["kommun_kod", "year"])
    g = panel.groupby("kommun_kod", group_keys=False)
    panel["befolkningstillvaxt_pct"] = 100 * g["folkmangd"].pct_change(fill_method=None)

    # All structural predictors are lagged one year so the explanatory value
    # precedes the migration outcome temporally.
    panel["lag1_inflyttning_per_1000"] = g["inflyttning_per_1000"].shift(1)
    panel["lag1_inflyttning_18_23_per_1000"] = g["inflyttning_18_23_per_1000"].shift(1)
    panel["lag1_inflyttning_63_68_per_1000"] = g["inflyttning_63_68_per_1000"].shift(1)
    panel["lag1_log_folkmangd"] = g["log_folkmangd"].shift(1)
    panel["lag1_befolkningstillvaxt_pct"] = g["befolkningstillvaxt_pct"].shift(1)
    panel["lag1_andel_20_34"] = g["andel_20_34"].shift(1)
    panel["lag1_inflyttare_medelalder"] = g["inflyttare_medelalder"].shift(1)
    panel["lag1_inkomst_tkr"] = g["inkomst_tkr"].shift(1)
    panel["lag1_andel_smahus"] = g["andel_smahus"].shift(1)
    panel["lag1_sysselsattningsgrad"] = g["sysselsattningsgrad"].shift(1)
    panel["lag1_arbetsloshet"] = g["arbetsloshet"].shift(1)
    panel["lag1_andel_eftergymnasial"] = g["andel_eftergymnasial"].shift(1)
    panel["lag1_andel_studerande"] = g["andel_studerande"].shift(1)
    panel["lag1_andel_industri_bc"] = g["andel_industri_bc"].shift(1)
    panel["lag1_andel_hotell_restaurang_i"] = g["andel_hotell_restaurang_i"].shift(1)
    panel["lag1_andel_kultur_service_rstu"] = g["andel_kultur_service_rstu"].shift(1)
    panel["lag1_log_externa_fa_jobb_per_1000"] = g["log_externa_fa_jobb_per_1000"].shift(1)

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
    "lag1_inflyttning_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_18_23_per_1000": "Historisk flyttdynamik",
    "lag1_inflyttning_63_68_per_1000": "Historisk flyttdynamik",
    "lag1_log_folkmangd": "Kommunstorlek",
    "lag1_befolkningstillvaxt_pct": "Befolkningsdynamik",
    "lag1_andel_20_34": "Åldersstruktur",
    "lag1_inflyttare_medelalder": "Inflyttarprofil",
    "lag1_inkomst_tkr": "Inkomstnivå",
    "lag1_andel_smahus": "Bostadsstruktur",
    "lag1_sysselsattningsgrad": "Arbetsmarknad",
    "lag1_arbetsloshet": "Arbetsmarknad",
    "lag1_andel_eftergymnasial": "Humankapital",
    "lag1_andel_studerande": "Studentmiljö",
    "lag1_andel_industri_bc": "Näringslivsprofil",
    "lag1_andel_hotell_restaurang_i": "Näringslivsprofil",
    "lag1_andel_kultur_service_rstu": "Näringslivsprofil",
    "lag1_log_externa_fa_jobb_per_1000": "Regional arbetsmarknadsaccess",
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
        "lag1_log_folkmangd",
        "lag1_befolkningstillvaxt_pct",
        "lag1_andel_20_34",
        "lag1_inflyttare_medelalder",
        "lag1_inkomst_tkr",
        "lag1_andel_smahus",
        "lag1_sysselsattningsgrad",
        "lag1_arbetsloshet",
        "lag1_andel_eftergymnasial",
        "lag1_andel_studerande",
        "lag1_andel_industri_bc",
        "lag1_andel_hotell_restaurang_i",
        "lag1_andel_kultur_service_rstu",
        "lag1_log_externa_fa_jobb_per_1000",
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

        validation_selection = _select_features(train, features, target)
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
            "Inkomst avser genomsnittlig sammanräknad förvärvsinkomst för 20–64-åringar och används laggad ett år.",
            "Andel småhus avser lägenheter i småhus dividerat med samtliga lägenheter i småhus, flerbostadshus, övriga hus och specialbostäder enligt SCB BO0104T04 och används laggad ett år.",
            "Arbetsmarknadsvariablerna är sysselsättningsgrad och arbetslöshet bland 20–64-åringar från SCB BAS och används laggade ett år.",
            "Utbildningsvariabeln är andel 25–64-åringar med eftergymnasial utbildning och används laggad ett år.",
            "Studentmiljö mäts som andel studerande bland 20–64-åringar enligt SCB IntGr8Kom1N och används laggad ett år.",
            "Näringslivsprofilen testas med andel sysselsatta efter arbetsställets belägenhet i B+C industri/gruvor, I hotell/restaurang samt R+S+T+U kultur/nöje/service enligt SCB ArRegUtb; högst en representant behålls från temat.",
            "Regional arbetsmarknadsaccess mäts som log(1 + jobb i övriga kommuner inom samma FA15-region per 1 000 invånare i den egna kommunen), laggad ett år.",
            "Variabelurvalet kombinerar Elastic Net, backward-AIC, tematisk diversifiering och tidsbaserad rolling-origin-korsvalidering.",
            "När flera variabler beskriver samma kvalitativa tema behålls högst en representant, vald efter inkrementellt AIC-bidrag.",
            "Tidsbaserad CV får endast sålla variabler när minst tre giltiga rolling-origin-foldar finns; annars behålls den tematiskt balanserade modellen.",
            "Alla strukturella förklaringsvariabler används laggade ett år för tydligare tidsordning mot inflyttningen.",
            "Variabelmatrisen redovisar parvis korrelation, gemensamt justerat R² samt extra justerat R² jämfört med den starkaste variabeln ensam.",
            "Tematisk marginalanalys tar bort ett valt tema i taget från fullmodellen och visar förändringen i justerat R², AIC och RMSE på samma analysurval.",
            "Separata livsfasmodeller skattas för 18–23 år och 63–68 år, med inflyttade per 1 000 invånare i samma åldersgrupp som mål och åldersgruppens egen föregående inflyttning som historisk dynamik.",
            "Om konsensusurvalet blir alltför litet används backward-AIC som reserv för att undvika instabila små modeller.",
            "Urvalet för prognosvalidering görs endast på träningsåren och får inte se teståret.",
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
        "lag1_log_folkmangd",
        "lag1_befolkningstillvaxt_pct",
        "lag1_andel_20_34",
        "lag1_inflyttare_medelalder",
        "lag1_inkomst_tkr",
        "lag1_andel_smahus",
        "lag1_sysselsattningsgrad",
        "lag1_arbetsloshet",
        "lag1_andel_eftergymnasial",
        "lag1_andel_studerande",
        "lag1_andel_industri_bc",
        "lag1_andel_hotell_restaurang_i",
        "lag1_andel_kultur_service_rstu",
        "lag1_log_externa_fa_jobb_per_1000",
    ]

    specs = {
        "18_23": {
            "label": "18–23 år",
            "interpretation": "Student-/etableringsålder",
            "target": "inflyttning_18_23_per_1000",
            "lag_target": "lag1_inflyttning_18_23_per_1000",
        },
        "63_68": {
            "label": "63–68 år",
            "interpretation": "Pensionsnära/pensionsövergång",
            "target": "inflyttning_63_68_per_1000",
            "lag_target": "lag1_inflyttning_63_68_per_1000",
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
            sel = _select_features(train, features, spec["target"])
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
    # Fetch the smaller auxiliary table first so API/schema failures are fast to diagnose.
    labor = get_labor_market()
    education = get_education()
    students = get_students()
    industry = get_industry_structure()
    fa15 = get_fa15_membership()
    mig = get_migration()
    pop = get_population()
    income = get_income()
    housing = get_housing()
    panel = build_panel(mig, pop, income, housing, labor, education, students, industry, fa15)
    panel.to_csv(OUT / "panel.csv", index=False)
    result = fit_models(panel)
    result["age_group_models"] = fit_age_group_models(panel)
    (OUT / "model.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
