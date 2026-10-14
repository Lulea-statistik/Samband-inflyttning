#!/usr/bin/env python3
"""Diagnose historical coverage bottlenecks independently for structural indicators."""
import json
from pathlib import Path
import pandas as pd
from audit_commuting_theme_candidates import THEMES
D=Path("docs/data")
def main():
    p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    p["kommun_kod"]=p.kommun_kod.str.zfill(4)
    model=json.loads((D/"model.json").read_text());target=model["target"]
    valid=set(p.loc[(p.year==2024)&p[target].notna(),"kommun_kod"].unique())
    if len(valid)!=290:raise RuntimeError("Cannot identify 290 municipalities")
    p=p[p.kommun_kod.isin(valid)]
    controls=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_inkomst_tkr",
      "lag1_andel_eftergymnasial","lag1_andel_fa_arbetsplatser_i_egen_kommun",
      "lag1_regional_centre_distance_km"]
    features=list(dict.fromkeys([target]+controls+THEMES["labor_dynamics"]+THEMES["civic_associations"]+
       ["lag1_naturpraglad_mark_andel_land_pct","lag1_strand_hav_bostader_tatort_per_1000",
        "lag1_smahuspris_medel_tkr","lag1_andel_bostader_70_max"]))
    result={"status":"historical_coverage_bottleneck_audit","production_model_changed":False,
      "n_municipalities":290,"features":{},"possible_fixed_5yr":{}}
    for col in features:
        if col not in p:
            result["features"][col]={"present":False};continue
        yearly={str(int(y)):int(t.loc[t[col].notna(),"kommun_kod"].nunique()) for y,t in p.groupby("year")}
        complete=sorted(int(y) for y,count in yearly.items() if count==290)
        eligible=[y for y in complete if all(z in complete for z in range(y-5,y))]
        result["features"][col]={"present":True,"complete_years":complete,"coverage_2010_onward":{y:n for y,n in yearly.items() if int(y)>=2010},"five_year_forecast_years":eligible}
    for group,cols in {"minimal":[target,"lag1_log_folkmangd","lag1_inkomst_tkr"],
                       "geographic":[target,"lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"],
                       "labor":[target,"lag1_log_folkmangd","lag1_inkomst_tkr","lag1_andel_fa_arbetsplatser_i_egen_kommun"]}.items():
        if not all(c in p for c in cols):continue
        complete=[int(y) for y,t in p.groupby("year") if t.dropna(subset=cols).kommun_kod.nunique()==290]
        result["possible_fixed_5yr"][group]=[y for y in complete if all(z in complete for z in range(y-5,y))]
    result["caution"]="Coverage is not source-definition harmonization; method breaks and availability at forecast origin require manual vetting before any fitting."
    (D/"structural_historical_bottlenecks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"five_year_count":{k:len(v.get("five_year_forecast_years",[])) for k,v in result["features"].items()},"controls":result["possible_fixed_5yr"]},ensure_ascii=False))
if __name__=="__main__":main()
