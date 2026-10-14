#!/usr/bin/env python3
"""Audit balanced municipality-year availability for all fair candidate features."""
import json
from pathlib import Path
import pandas as pd
D=Path("docs/data")
def main():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    model=json.loads((D/"model.json").read_text(encoding="utf-8"))
    target=model["target"]
    registry=json.loads((D/"fair_variable_thematic_register.json").read_text(encoding="utf-8"))
    eligible=set(panel.loc[(panel.year==2024)&panel[target].notna(),"kommun_kod"].unique())
    if len(eligible)!=290:raise RuntimeError("Expected precisely 290 municipalities")
    panel=panel.loc[panel.kommun_kod.isin(eligible)].copy()
    years=sorted(int(y) for y in panel.year.unique())
    if not years:raise RuntimeError("No years")
    entries=[]
    for item in registry["records"]:
        name=item["feature"]
        exists=name in panel
        coverage={}
        for y in years:
            rows=panel.loc[panel.year==y]
            coverage[str(y)]=int(rows.loc[rows[name].notna(),"kommun_kod"].nunique()) if exists else 0
        complete=[y for y in years if coverage[str(y)]==290]
        windows={str(window):[y for y in complete if all(t in complete for t in range(y-window,y))]
                 for window in (3,5,10)}
        entries.append({"feature":name,"theme":item["theme"],
          "original_candidate_pool":item["original_candidate_pool"],
          "newly_discovered":item["newly_discovered"],
          "first_complete_year":min(complete) if complete else None,
          "last_complete_year":max(complete) if complete else None,
          "fully_covered_years":complete,"yearly_municipalities":coverage,
          "possible_forecast_years":windows,
          "historical_coverage_status":"complete_windows_available" if windows["5"] else
              ("short_history" if complete else "no_complete_year"),
          "as_of_publication_status":"not_verified",
          "historical_release_safe":False})
    if len(entries)!=73:raise RuntimeError("Expected 73 candidates; got "+str(len(entries)))
    summary={"candidates":len(entries),"five_year_eligible":sum(bool(x["possible_forecast_years"]["5"]) for x in entries),
             "three_year_eligible":sum(bool(x["possible_forecast_years"]["3"]) for x in entries),
             "ten_year_eligible":sum(bool(x["possible_forecast_years"]["10"]) for x in entries),
             "historical_publication_verified":0}
    result={"status":"fair_all_candidate_historical_coverage",
      "municipalities":290,"years":years,"window_definition":"Each eligible forecast year has N prior fully covered municipality-years AND full forecast-year coverage; no source release dates checked.",
      "summary":summary,"features":entries,
      "production_model_changed":False,
      "limitations":["Completeness does not prove historical as-of availability or consistent measurement definition.",
          "A forecast-year list for each feature does not imply that the same years are complete for any multivariable model.",
          "Calendar panel has current restated values; do not treat 2023-2024 as untouched holdout.",
          "No regression or automatic feature selection performed."]}
    (D/"fair_all_candidate_historical_coverage.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
