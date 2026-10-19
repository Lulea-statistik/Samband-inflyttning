#!/usr/bin/env python3
"""Robustness audit for the fixed population-reliability blend.

No tuning. Reads already generated blend predictions and evaluates:
- year-by-year RMSE/MAE/p95/max
- how often blend beats core4
- worst deterioration/improvement municipalities
- Lulea comparison
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
P=D/"three_year_forecast_core4_population_reliability_blend_predictions.csv"
OUT=D/"three_year_forecast_core4_population_reliability_blend_robustness.json"

p=pd.read_csv(P,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)

def met(df,col):
    e=df[col].to_numpy()-df["actual"].to_numpy()
    ae=np.abs(e)
    return {
      "n":int(len(e)),
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(ae)),
      "bias":float(np.mean(e)),
      "p95_abs_error":float(np.quantile(ae,.95)),
      "max_abs_error":float(np.max(ae))
    }

yearly=[]
for y,g in p.groupby("year"):
    a=met(g,"prediction")
    b=met(g,"population_reliability_blend")
    yearly.append({
      "year":int(y),
      "core4":a,
      "blend":b,
      "rmse_change_pct":100*(b["rmse"]/a["rmse"]-1),
      "p95_change_pct":100*(b["p95_abs_error"]/a["p95_abs_error"]-1),
      "rmse_better":b["rmse"]<a["rmse"],
      "p95_better":b["p95_abs_error"]<a["p95_abs_error"]
    })

p["core4_abs_error"]=(p["prediction"]-p["actual"]).abs()
p["blend_abs_error"]=(p["population_reliability_blend"]-p["actual"]).abs()
p["abs_error_change"]=p["blend_abs_error"]-p["core4_abs_error"]

by_muni=(p.groupby("kommun_kod").agg(
  years=("year","count"),
  core4_mae=("core4_abs_error","mean"),
  blend_mae=("blend_abs_error","mean"),
  mean_abs_error_change=("abs_error_change","mean"),
  worst_abs_error_change=("abs_error_change","max"),
  best_abs_error_change=("abs_error_change","min"),
  population=("population","mean"),
  mean_core4_weight=("core4_weight","mean")
).reset_index())
by_muni["improved_mean"]=by_muni["blend_mae"]<by_muni["core4_mae"]

l=p[p["kommun_kod"].eq("2580")].copy()
lulea={
 "core4_mae":float(l["core4_abs_error"].mean()),
 "blend_mae":float(l["blend_abs_error"].mean()),
 "mae_change_pct":float(100*(l["blend_abs_error"].mean()/l["core4_abs_error"].mean()-1)),
 "years_blend_better":int((l["blend_abs_error"]<l["core4_abs_error"]).sum()),
 "years_total":int(len(l))
}

res={
 "status":"core4_population_reliability_blend_robustness",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "parameter_tuning":False,
 "yearly":yearly,
 "year_summary":{
   "years_total":len(yearly),
   "years_rmse_better":sum(x["rmse_better"] for x in yearly),
   "years_p95_better":sum(x["p95_better"] for x in yearly)
 },
 "municipality_summary":{
   "municipalities_total":int(len(by_muni)),
   "municipalities_improved_mean_mae":int(by_muni["improved_mean"].sum()),
   "share_improved_mean_mae":float(by_muni["improved_mean"].mean())
 },
 "largest_mean_improvements":by_muni.sort_values("mean_abs_error_change").head(20).to_dict("records"),
 "largest_mean_deteriorations":by_muni.sort_values("mean_abs_error_change",ascending=False).head(20).to_dict("records"),
 "largest_single_year_deteriorations":p.sort_values("abs_error_change",ascending=False).head(20)[
   ["year","kommun_kod","actual","prediction","population_reliability_blend",
    "core4_abs_error","blend_abs_error","abs_error_change","population","core4_weight"]
 ].to_dict("records"),
 "lulea":lulea,
 "decision_note":"This is a robustness audit of the already fixed C=10000 blend; it does not tune or alter the blend."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({
 "year_summary":res["year_summary"],
 "municipality_summary":res["municipality_summary"],
 "lulea":lulea,
 "yearly":yearly
},ensure_ascii=False,indent=2))
