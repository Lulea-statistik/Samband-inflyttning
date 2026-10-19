#!/usr/bin/env python3
"""Exploratory population-reliability blend for frozen core-4.

Motivation from the geographic diagnostic:
- core-4 error is much larger in the smallest municipalities;
- error also rises at very high lagged inflow levels;
- broad county/geographic residual corrections were not robust.

This study does NOT change core-4. It tests a second-stage reliability blend:
  adjusted = w * core4 + (1-w) * lag1_inflow
where
  w = population / (population + C)

C is fixed at 10,000 inhabitants before evaluation. This gives more persistence
weight to small municipalities, where per-1000 rates are noisier, while leaving
large municipalities close to core-4.

No parameter tuning is performed in this script. Research-only.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
PRED=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
PANEL=D/"panel.csv"
OUT=D/"three_year_forecast_core4_population_reliability_blend.json"
OUTCSV=D/"three_year_forecast_core4_population_reliability_blend_predictions.csv"

C=10000.0
YEARS=list(range(2019,2025))

pred=pd.read_csv(PRED,dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)
pred=pred[(pred["window_years"].eq(6)) & (pred["forecast_year"].isin(YEARS))].copy()
pred=pred.rename(columns={"forecast_year":"year"})

panel=pd.read_csv(PANEL,dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
need=["lag1_inflyttning_per_1000","lag1_log_folkmangd"]
for c in need:
    if c not in panel.columns:
        raise SystemExit(f"Missing {c}")
    panel[c]=pd.to_numeric(panel[c],errors="coerce")

x=panel[["kommun_kod","year"]+need].copy()
pred=pred.merge(x,on=["kommun_kod","year"],how="left",validate="one_to_one")
if pred[need].isna().any().any():
    raise SystemExit("Missing reliability-blend inputs")

# lag1_log_folkmangd is natural log population.
pred["population"]=np.exp(pred["lag1_log_folkmangd"])
pred["core4_weight"]=pred["population"]/(pred["population"]+C)
pred["population_reliability_blend"]=(
    pred["core4_weight"]*pred["prediction"]+
    (1-pred["core4_weight"])*pred["lag1_inflyttning_per_1000"]
)

def met(df,col):
    e=df[col].to_numpy()-df["actual"].to_numpy()
    ae=np.abs(e)
    return {
      "n":int(len(e)),
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(ae)),
      "bias_prediction_minus_actual":float(np.mean(e)),
      "median_absolute_error":float(np.median(ae)),
      "p90_absolute_error":float(np.quantile(ae,.90)),
      "p95_absolute_error":float(np.quantile(ae,.95)),
      "max_absolute_error":float(np.max(ae)),
      "share_abs_error_gt_10":float(np.mean(ae>10))
    }

summary={
  "core4":met(pred,"prediction"),
  "lag1_persistence":met(pred,"lag1_inflyttning_per_1000"),
  "population_reliability_blend":met(pred,"population_reliability_blend")
}
base=summary["core4"]
for name in ["lag1_persistence","population_reliability_blend"]:
    summary[name]["rmse_change_vs_core4_pct"]=100*(summary[name]["rmse"]/base["rmse"]-1)
    summary[name]["p95_abs_error_change_vs_core4_pct"]=100*(summary[name]["p95_absolute_error"]/base["p95_absolute_error"]-1)
    summary[name]["max_abs_error_change_vs_core4_pct"]=100*(summary[name]["max_absolute_error"]/base["max_absolute_error"]-1)

# Population deciles within year for diagnostic comparison.
pred["population_decile"]=0
for y,g in pred.groupby("year"):
    bins=pd.qcut(g["population"].rank(method="first"),10,labels=False)+1
    pred.loc[g.index,"population_decile"]=bins.astype(int)

by_decile=[]
for d,g in pred.groupby("population_decile"):
    by_decile.append({
      "population_decile":int(d),
      "n":int(len(g)),
      "core4":met(g,"prediction"),
      "blend":met(g,"population_reliability_blend"),
      "mean_core4_weight":float(g["core4_weight"].mean())
    })

l=pred[pred["kommun_kod"].eq("2580")]
lulea=[]
for _,r in l.iterrows():
    lulea.append({
      "year":int(r["year"]),
      "actual":float(r["actual"]),
      "population":float(r["population"]),
      "core4_weight":float(r["core4_weight"]),
      "core4":float(r["prediction"]),
      "core4_error":float(r["prediction"]-r["actual"]),
      "lag1_persistence":float(r["lag1_inflyttning_per_1000"]),
      "blend":float(r["population_reliability_blend"]),
      "blend_error":float(r["population_reliability_blend"]-r["actual"])
    })

res={
 "status":"core4_population_reliability_blend_exploratory",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":YEARS,
 "n_municipalities":290,
 "design":{
   "formula":"blend = w*core4 + (1-w)*lag1_inflow",
   "weight":"w = population/(population+10000)",
   "C_fixed":C,
   "rationale":"smaller municipalities have noisier per-1000 rates; shrink them more toward observed lag1 persistence",
   "parameter_tuning":False
 },
 "summary":summary,
 "by_population_decile":by_decile,
 "lulea":lulea,
 "decision_rule":"Exploratory only. Consider promising only if overall RMSE and upper-tail errors both improve, with gains concentrated in smaller municipalities and no material degradation for large municipalities."
}
pred.to_csv(OUTCSV,index=False)
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"summary":summary,"lulea":lulea},ensure_ascii=False,indent=2))
