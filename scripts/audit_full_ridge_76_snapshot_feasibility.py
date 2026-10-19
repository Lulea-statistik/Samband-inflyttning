#!/usr/bin/env python3
"""Audit whether a complete 76-feature full-Ridge predictor snapshot can be frozen.

No fitting, no selection, no production change.
Checks existing panel rows by target year against the exact frozen 76-feature order.
"""
import json
from pathlib import Path
import pandas as pd

D=Path("docs/data")
m=json.loads((D/"three_year_forecast_pre_outcome_frozen_models.json").read_text(encoding="utf-8"))
features=m["full_ridge_benchmark"]["features"]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)

# Employment research columns used in frozen benchmark live in a separate file.
emp_path=D/"employment_lag1_research_availability.csv"
if emp_path.exists():
    emp=pd.read_csv(emp_path,dtype={"kommun_kod":str})
    emp["kommun_kod"]=emp["kommun_kod"].astype(str).str.zfill(4)
    extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
           .reset_index()
           .rename(columns={
             "target_year":"year",
             "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
             "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"
           }))
    panel=panel.merge(extra,on=["year","kommun_kod"],how="left")

years=sorted(int(y) for y in panel["year"].dropna().unique())
rows=[]
for year in years:
    q=panel[panel.year==year]
    if q.empty: continue
    rec={"target_year":year,"municipalities":int(q.kommun_kod.nunique())}
    complete=[]
    missing=[]
    for f in features:
        if f not in q.columns:
            n=0
        else:
            n=int(q[f].notna().sum())
        if n==290:
            complete.append(f)
        else:
            missing.append({"feature":f,"non_null":n,"missing":290-n})
    rec["complete_features"]=len(complete)
    rec["missing_features_count"]=len(missing)
    rec["all_76_complete"]=len(missing)==0 and rec["municipalities"]==290
    rec["missing_features"]=missing
    rows.append(rec)

# latest fully complete and latest available year
full_years=[r["target_year"] for r in rows if r["all_76_complete"]]
out={
 "status":"full_ridge_76_predictor_snapshot_feasibility_audit",
 "production_changed":False,
 "feature_count":len(features),
 "years":rows,
 "latest_panel_year":max(years) if years else None,
 "latest_complete_76_year":max(full_years) if full_years else None,
 "decision":{
   "can_freeze_complete_76_matrix_from_existing_panel_for_latest_year":bool(rows and rows[-1]["all_76_complete"]),
   "note":"Completeness is necessary but not sufficient for strict as-of validity; each future predictor row must also be available before outcome inspection."
 }
}
(D/"three_year_forecast_full_ridge_76_snapshot_feasibility.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "latest_panel_year":out["latest_panel_year"],
 "latest_complete_76_year":out["latest_complete_76_year"],
 "latest":rows[-1] if rows else None
},ensure_ascii=False,indent=2))
