#!/usr/bin/env python3
"""Audit historical RAMS/BAS lag-1 availability and historical forecast-feature coverage.
No models are trained and production is unchanged.
"""
import json
from pathlib import Path
import pandas as pd

ROOT=Path("docs/data")
raw=pd.read_csv(ROOT/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
raw["kommun_kod"]=raw.kommun_kod.str.zfill(4)
if raw.duplicated(["kommun_kod","year"]).any():raise ValueError("Duplicated RAMS municipality-year")
assert len(raw)==5220 and raw.kommun_kod.nunique()==290
panel=pd.read_csv(ROOT/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
ram=raw[["kommun_kod","year","regime","outcommuting_share_pct"]].rename(columns={"outcommuting_share_pct":"lag1_rams_outcommuting_share"})
ram["year"]+=1
d=panel.merge(ram,on=["kommun_kod","year"],how="left",validate="many_to_one")
model=json.loads((ROOT/"model.json").read_text())
fair=model.get("fair_reselection_test",{})
inc=list(fair.get("incumbent_features",[]))
available=[f for f in inc if f in d.columns]
missing=[f for f in inc if f not in d.columns]
periods={"pre2019_RAMS":list(range(2005,2020)),"post2019_RAMS":list(range(2020,2023)),"BAS":list(range(2021,2025))}
report={"status":"coverage_audit_only","lag_alignment":"RAMS reference year t-1 predicts migration outcome t","periods":{},
"incumbent_feature_count":len(inc),"incumbent_missing_columns":missing,
"method_breaks":"RAMS 2018/19, RAMS versus BAS 2020-21 overlap; do not pool without break controls",
"production_model_changed":False}
for name,years in periods.items():
    rows=[]
    for yr in years:
        frame=d[d.year==yr]
        usable=frame[frame.lag1_rams_outcommuting_share.notna()] if name!="BAS" else frame
        rows.append({"year":yr,"observations_with_RAMS_lag":int(frame.lag1_rams_outcommuting_share.notna().sum()),
                     "complete_incumbent_and_RAMS":int(frame[available+["lag1_rams_outcommuting_share"]].notna().all(axis=1).sum()) if available else 0,
                     "incumbent_features_with_250_valid":[f for f in available if usable[f].notna().sum()>=250]})
    report["periods"][name]=rows
(ROOT/"commuting_historical_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":report["status"],"period_ranges":{k:[v[0]["year"],v[-1]["year"]] for k,v in report["periods"].items()}},ensure_ascii=False))
