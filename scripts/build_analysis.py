#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
import re
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
HOUSING_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T02"
LABOR_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210A/ArbStatusAr"
EDUCATION_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/UF/UF0506/UF0506B/Utbildning"
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
    r = session.post(url, json=payload, timeout=180)
    if not r.ok:
        raise RuntimeError(
            f"SCB query failed {r.status_code} for {url}: {r.text[:1000]} "
            f"| selections={json.dumps(selections, ensure_ascii=False)}"
        )
    return pd.read_csv(io.StringIO(r.text), sep=None, engine="python")


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
        if (np.isfinite(a) and 20 <= a <= 34) or "tot" in str(text).lower():
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
    """Share of dwelling stock located in small houses."""
    meta = metadata(HOUSING_URL)
    region = find_var(meta, "region")
    house_type = find_var(meta, "hustyp")
    period = find_var(meta, "byggnadsperiod", "byggnadsår", "byggnadsar")
    time = find_var(meta, "år", "tid")

    # Some PxWeb tables expose a separate content dimension, others only one measure.
    content = None
    try:
        content = find_var(meta, "tabellinnehåll", "contentscode")
    except KeyError:
        pass

    munis = municipality_codes(region)
    small_code = exact_or_contains_code(house_type, "småhus")
    total_house_codes = aggregate_codes(house_type)
    period_codes = aggregate_codes(period)

    rows = []
    for year in AUX_YEARS:
        selections = {
            region["code"]: munis,
            house_type["code"]: list(dict.fromkeys(total_house_codes + [small_code])),
            period["code"]: period_codes,
            time["code"]: [str(year)],
        }
        if content is not None:
            selections[content["code"]] = [content["values"][0]]

        df = px_csv(HOUSING_URL, selections)
        dims = standardize_columns(df)
        # Add table-specific dimensions if the generic recognizer does not know them.
        for c in df.columns:
            cl = str(c).lower()
            if "hustyp" in cl:
                dims["house_type"] = c
            elif "byggnadsperiod" in cl or "byggnadsår" in cl or "byggnadsar" in cl:
                dims["period"] = c
        dim_cols = set(dims.values())
        value_cols = [c for c in df.columns if c not in dim_cols]
        if len(value_cols) != 1:
            raise ValueError(f"Expected one housing value column for {year}, got {value_cols}")
        val_col = value_cols[0]
        df["value"] = normalize_number(df[val_col])
        df["year"] = year
        df[["kommun_kod", "kommun"]] = df[dims["region"]].apply(lambda x: pd.Series(split_region(x)))

        hcol = dims["house_type"]
        df["_is_small"] = df[hcol].astype(str).str.lower().str.contains("småhus", regex=False)
        # If the table has an explicit total category, use that for denominator;
        # otherwise sum all component house types.
        house_texts = [str(x).strip().lower() for x in df[hcol].dropna().unique()]
        total_labels = [x for x in house_texts if x in {"totalt","total","samtliga","alla"} or "totalt" in x]
        if total_labels:
            totals = df[df[hcol].astype(str).str.lower().isin(total_labels)].groupby(
                ["kommun_kod","kommun","year"], as_index=False
            )["value"].sum().rename(columns={"value":"bostader_totalt"})
        else:
            totals = df.groupby(["kommun_kod","kommun","year"], as_index=False)["value"].sum().rename(
                columns={"value":"bostader_totalt"}
            )
        small = df[df["_is_small"]].groupby(
            ["kommun_kod","kommun","year"], as_index=False
        )["value"].sum().rename(columns={"value":"bostader_smahus"})
        agg = totals.merge(small, on=["kommun_kod","kommun","year"], how="left")
        agg["andel_smahus"] = 100 * agg["bostader_smahus"] / agg["bostader_totalt"].replace(0, np.nan)
        rows.append(agg[["kommun_kod","kommun","year","andel_smahus"]])
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
    for year in AUX_YEARS:
        df = px_csv(EDUCATION_URL, {
            region["code"]: munis,
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


def build_panel(mig: pd.DataFrame, pop: pd.DataFrame, income: pd.DataFrame, housing: pd.DataFrame, labor: pd.DataFrame, education: pd.DataFrame) -> pd.DataFrame:
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

    panel = mg.merge(total, on=["kommun_kod", "kommun", "year"], how="left")
    panel = panel.merge(young, on=["kommun_kod", "kommun", "year"], how="left")
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
    panel["andel_20_34"] = 100 * panel["bef_20_34"] / panel["folkmangd"]
    panel["inflyttning_per_1000"] = 1000 * panel["inflyttade"] / panel["folkmangd"]

    panel = panel.sort_values(["kommun_kod", "year"])
    g = panel.groupby("kommun_kod", group_keys=False)
    panel["lag1_inflyttning_per_1000"] = g["inflyttning_per_1000"].shift(1)
    panel["lag1_inflyttare_medelalder"] = g["inflyttare_medelalder"].shift(1)
    panel["lag1_inkomst_tkr"] = g["inkomst_tkr"].shift(1)
    panel["lag1_andel_smahus"] = g["andel_smahus"].shift(1)
    panel["lag1_sysselsattningsgrad"] = g["sysselsattningsgrad"].shift(1)
    panel["lag1_arbetsloshet"] = g["arbetsloshet"].shift(1)
    panel["lag1_andel_eftergymnasial"] = g["andel_eftergymnasial"].shift(1)
    panel["befolkningstillvaxt_pct"] = 100 * g["folkmangd"].pct_change(fill_method=None)
    panel["log_folkmangd"] = np.log(panel["folkmangd"].where(panel["folkmangd"] > 0))

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


def _select_features(
    d: pd.DataFrame,
    features: list[str],
    target: str,
) -> dict:
    elastic, elastic_meta = _elastic_net_selection(d, features, target)
    backward, backward_history = _backward_aic_selection(d, features, target)

    consensus = [f for f in features if f in elastic and f in backward]
    # Avoid an over-aggressive selector in small windows.
    if len(consensus) < 2:
        consensus = list(backward)
    if not consensus:
        consensus = [features[0]]

    excluded = [f for f in features if f not in consensus]
    return {
        "selected": consensus,
        "excluded": excluded,
        "elastic_net_selected": elastic,
        "backward_aic_selected": backward,
        "elastic_net": elastic_meta,
        "backward_aic_history": backward_history,
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
        "standard_errors": "Klustrade per kommun",
        "year_fixed_effects": True,
    }
    return result, diag, qq


def fit_models(panel: pd.DataFrame) -> dict:
    target = "inflyttning_per_1000"
    features = [
        "lag1_inflyttning_per_1000",
        "log_folkmangd",
        "befolkningstillvaxt_pct",
        "andel_20_34",
        "lag1_inflyttare_medelalder",
        "lag1_inkomst_tkr",
        "lag1_andel_smahus",
        "lag1_sysselsattningsgrad",
        "lag1_arbetsloshet",
        "lag1_andel_eftergymnasial",
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
            "Andel småhus avser bostadslägenheter i småhus som andel av bostadsbeståndet och används laggad ett år.",
            "Arbetsmarknadsvariablerna är sysselsättningsgrad och arbetslöshet bland 20–64-åringar från SCB BAS och används laggade ett år.",
            "Utbildningsvariabeln är andel 25–64-åringar med eftergymnasial utbildning och används laggad ett år.",
            "Variabelurvalet kombinerar Elastic Net och backward-AIC; variabler som väljs av båda behålls i första hand.",
            "Om konsensusurvalet blir alltför litet används backward-AIC som reserv för att undvika instabila små modeller.",
            "Urvalet för prognosvalidering görs endast på träningsåren och får inte se teståret.",
            "Samband ska inte tolkas som säkra kausala effekter; endogenitet och utelämnade variabler kan finnas.",
        ],
    }


def main():
    # Fetch the smaller auxiliary table first so API/schema failures are fast to diagnose.
    labor = get_labor_market()
    education = get_education()
    mig = get_migration()
    pop = get_population()
    income = get_income()
    housing = get_housing()
    panel = build_panel(mig, pop, income, housing, labor, education)
    panel.to_csv(OUT / "panel.csv", index=False)
    result = fit_models(panel)
    (OUT / "model.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
