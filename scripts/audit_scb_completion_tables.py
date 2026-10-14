#!/usr/bin/env python3
"""Compare SCB completed dwelling counts by completion year; never modify panel."""
import json
from pathlib import Path
import pandas as pd
from build_analysis import (metadata, find_var, municipality_codes, px_csv,
    standardize_columns, normalize_number, split_region, get_completed_housing)
D=Path("docs/data")
ALTERNATE="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0101/BO0101A/LghReHustypAr"
def main():
    m=metadata(ALTERNATE)
    region=find_var(m,"region")
    house=find_var(m,"hustyp")
    years=find_var(m,"år","tid")
    contents=next((v for v in m["variables"] if "tabellinnehåll" in v.get("text","").lower() or "contentscode" in v.get("code","").lower()),None)
    available=set(years["values"])
    target=[str(y) for y in (2021,2022,2023,2024) if str(y) in available]
    if not target:raise RuntimeError("No overlap years available")
    # Select apartment counts, not room units. Preserve SCB year as completion year.
    selections={region["code"]:municipality_codes(region),house["code"]:list(house["values"]),years["code"]:target}
    if contents:
        texts=contents.get("valueTexts",[])
        hits=[code for code,txt in zip(contents["values"],texts) if "lägenheter" in str(txt).lower() and "rumsenheter" not in str(txt).lower()]
        if len(hits)!=1:raise RuntimeError("Ambiguous apartment measure: "+str(list(zip(contents["values"],texts))))
        selections[contents["code"]]=hits
    raw=px_csv(ALTERNATE,selections)
    dims=standardize_columns(raw)
    for c in raw.columns:
        if "hustyp" in str(c).lower():dims["house_type"]=c
    value_cols=[c for c in raw if c not in set(dims.values())]
    # SCB returns a wide CSV (one value column per year) for multi-year requests.
    if len(value_cols)>1:
        import re
        year_col={}
        for col in value_cols:
            matched=re.search(r"(?:19|20)\d{2}$",str(col))
            if not matched:raise RuntimeError("Unrecognized value-column year: "+str(col))
            year_col[col]=int(matched.group())
        if len(set(year_col.values()))!=len(value_cols):
            raise RuntimeError("Duplicate year value columns")
        raw=raw.melt(id_vars=[c for c in raw if c not in value_cols],
            value_vars=value_cols,var_name="_year_source",value_name="_count_source")
        raw["year"]=raw["_year_source"].map(year_col)
        raw["count"]=normalize_number(raw["_count_source"])
    elif len(value_cols)==1:
        raw["count"]=normalize_number(raw[value_cols[0]])
        raw["year"]=pd.to_numeric(raw[dims["time"]],errors="coerce")
    else:raise RuntimeError("No apartment count value columns")
    if raw["year"].isna().any():raise RuntimeError("Missing completion years")
    raw[["kommun_kod","kommun"]]=raw[dims["region"]].apply(lambda x:pd.Series(split_region(x)))
    alternative=raw.groupby(["kommun_kod","year"],as_index=False)["count"].sum(min_count=1).rename(columns={"count":"alternate"})
    # Existing series uses the exact same SCB completion-year convention.
    original=get_completed_housing().rename(columns={"fardigstallda_bostader":"original"})
    original=original[["kommun_kod","year","original"]]
    paired=original.merge(alternative,on=["kommun_kod","year"],how="outer",indicator=True)
    compare=paired.loc[paired.year.isin([int(y) for y in target])].copy()
    matched=compare.loc[compare["_merge"].eq("both")&compare.original.notna()&compare.alternate.notna()].copy()
    matched["difference"]=matched.alternate-matched.original
    exceptions=matched.loc[matched.difference.ne(0)].sort_values(["year","kommun_kod"])
    missing=compare.loc[compare["_merge"].ne("both")|compare.original.isna()|compare.alternate.isna()]
    summary={"status":"scb_completion_year_cross_table_quality_check",
      "production_changed":False,"tables":{"existing":"LghReHtypUfAr","cross_check":"LghReHustypAr"},
      "years":sorted(int(y) for y in target),"matched_rows":len(matched),
      "different_rows":len(exceptions),"missing_rows":len(missing),
      "by_year":{str(y):{"matched":int((matched.year==int(y)).sum()),"different":int((exceptions.year==int(y)).sum()),"missing":int((missing.year==int(y)).sum())} for y in target},
      "discrepancies":exceptions[["kommun_kod","year","original","alternate","difference"]].to_dict("records"),
      "missing_examples":missing[["kommun_kod","year","original","alternate","_merge"]].head(80).to_dict("records"),
      "limitations":["SCB can revise historical counts; same-year agreement does not establish as-of historical publication availability.",
        "Source counts retain the SCB completion reference year; this audit never shifts years.",
        "No original model data or production is modified."]}
    (D/"scb_completed_housing_table_crosscheck.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("matched_rows","different_rows","missing_rows","by_year")},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
