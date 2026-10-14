#!/usr/bin/env python3
"""Audit time-safe employment level, growth and anomaly candidates before model fitting."""
import json
from pathlib import Path
import pandas as pd
from test_commuting_annual_paired import source_data
D=Path("docs/data")
def main():
    sources,fair,target=source_data()
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    cols=[x for x in panel.columns if ("sysselsatta" in x or "sysselsatt" in x) and ("bostad" in x or "arbetsstalle" in x)]
    records=[]
    for col in cols:
        records.append({"variable":col,"coverage":{str(y):int(panel.loc[panel.year==y,col].notna().sum()) for y in (2019,2020,2021,2022,2023,2024) if y in set(panel.year)}})
    growth="lag1_sysselsatta_bostad_forandring_pct"
    d=panel[["kommun_kod","year",growth]].copy()
    # Historical growth values only from prior forecast years; no future leak.
    for lag in (1,2,3):
        prev=d[["kommun_kod","year",growth]].copy()
        prev.year+=lag
        prev=prev.rename(columns={growth:f"prior_{lag}_growth"})
        d=d.merge(prev,on=["kommun_kod","year"],how="left",validate="one_to_one")
    d["prior_2y_mean"]=d[["prior_1_growth","prior_2_growth"]].mean(axis=1,skipna=False)
    d["anomaly_2y"]=d[growth]-d.prior_2y_mean
    report={"status":"employment_representation_availability","target":target,
      "variables":records,"growth_lag_history":{
        str(year):{col:int(d.loc[d.year==year,col].notna().sum()) for col in (growth,"prior_1_growth","prior_2_growth","prior_3_growth","prior_2y_mean","anomaly_2y")}
        for year in (2022,2023,2024)},
      "caution":"Prior growth is taken from rows for earlier forecast years and is never computed using future-year outcomes.",
      "production_model_changed":False}
    (D/"commuting_employment_representation_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
