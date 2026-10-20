#!/usr/bin/env python3
"""Dispersion-aware post-processing challenger for frozen core-4.

Uses only already frozen historical core-4 predictions and earlier forecast-year
outcomes. No core-4 refit, no feature reselection, no contemporaneous outcome use.

For each forecast year, test a small grid of shrinkage strengths that pull each
municipality prediction toward that year's cross-sectional median prediction.
The shrinkage strength is selected using only earlier forecast years to minimize
a pre-specified combined objective:
  pooled RMSE + gamma * p90 municipality RMSE
where municipality RMSE is computed across the available historical forecast years.

This directly targets geographic dispersion while keeping the structural model frozen.
"""
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
P=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
OUT=D/"core4_geographic_equity_weighted_challenger.json"
OUTCSV=D/"core4_geographic_equity_weighted_challenger_predictions.csv"

WINDOW=6
EVAL_YEARS=list(range(2020,2025))
LAMBDAS=[0.0,0.05,0.10,0.15,0.20,0.30]
GAMMAS=[0.0,0.25,0.50,1.0]

p=pd.read_csv(P,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[p["window_years"].eq(WINDOW)].copy().rename(columns={"forecast_year":"year"})
if p.groupby("year")["kommun_kod"].nunique().min()!=290:
    raise SystemExit("Incomplete six-year rolling-origin prediction panel")

def metrics(df,pred_col):
    e=(df[pred_col]-df["actual"]).to_numpy(float)
    pooled_rmse=float(np.sqrt(np.mean(e*e)))
    pooled_mae=float(np.mean(np.abs(e)))
    tmp=df.assign(_e=e).groupby("kommun_kod")["_e"].apply(
        lambda x: float(np.sqrt(np.mean(np.square(x.to_numpy(float))))))
    vals=tmp.to_numpy(float)
    return {
      "n":int(len(df)),
      "pooled_rmse":pooled_rmse,
      "pooled_mae":pooled_mae,
      "mean_municipality_rmse":float(np.mean(vals)),
      "median_municipality_rmse":float(np.quantile(vals,.5)),
      "sd_municipality_rmse":float(np.std(vals,ddof=1)),
      "p90_municipality_rmse":float(np.quantile(vals,.9)),
      "p95_municipality_rmse":float(np.quantile(vals,.95)),
      "worst_decile_mean_rmse":float(np.mean(np.sort(vals)[-29:])),
      "max_municipality_rmse":float(np.max(vals)),
      "share_municipalities_rmse_gt_10":float(np.mean(vals>10))
    }

def apply_lambda(df,lam):
    z=df.copy()
    med=z.groupby("year")["prediction"].transform("median")
    z["challenger_prediction"]=(1-lam)*z["prediction"]+lam*med
    return z

# Select lambda out-of-time using only earlier forecast years.
rows=[]
selections=[]
for y in EVAL_YEARS:
    hist=p[p["year"]<y].copy()
    te=p[p["year"].eq(y)].copy()
    if hist["year"].nunique()<3:
        raise SystemExit(f"Insufficient historical forecast years before {y}")
    for gamma in GAMMAS:
        scored=[]
        for lam in LAMBDAS:
            h=apply_lambda(hist,lam)
            m=metrics(h,"challenger_prediction")
            obj=m["pooled_rmse"]+gamma*m["p90_municipality_rmse"]
            scored.append((obj,lam,m))
        scored.sort(key=lambda t:(t[0],t[1]))
        best_obj,best_lam,best_hist=scored[0]
        z=apply_lambda(te,best_lam)
        for _,r in z.iterrows():
            rows.append({
              "gamma":gamma,
              "year":int(y),
              "kommun_kod":r["kommun_kod"],
              "actual":float(r["actual"]),
              "core4":float(r["prediction"]),
              "challenger":float(r["challenger_prediction"]),
              "selected_lambda":best_lam
            })
        selections.append({
          "gamma":gamma,"year":y,"selected_lambda":best_lam,
          "historical_objective":best_obj,
          "historical_pooled_rmse":best_hist["pooled_rmse"],
          "historical_p90_municipality_rmse":best_hist["p90_municipality_rmse"]
        })

o=pd.DataFrame(rows)
o.to_csv(OUTCSV,index=False)

summary={}
for gamma in GAMMAS:
    q=o[o["gamma"].eq(gamma)].copy()
    base=q.rename(columns={"core4":"_pred"})
    chal=q.rename(columns={"challenger":"_pred"})
    bm=metrics(base.rename(columns={"_pred":"core4"}),"core4")
    cm=metrics(chal.rename(columns={"_pred":"challenger"}),"challenger")
    cm["delta_vs_core4_pct"]={
      "pooled_rmse":100*(cm["pooled_rmse"]/bm["pooled_rmse"]-1),
      "p90_municipality_rmse":100*(cm["p90_municipality_rmse"]/bm["p90_municipality_rmse"]-1),
      "worst_decile_mean_rmse":100*(cm["worst_decile_mean_rmse"]/bm["worst_decile_mean_rmse"]-1),
      "sd_municipality_rmse":100*(cm["sd_municipality_rmse"]/bm["sd_municipality_rmse"]-1)
    }
    summary[str(gamma)]={"core4":bm,"challenger":cm}

promising=[]
for gamma in GAMMAS:
    d=summary[str(gamma)]["challenger"]["delta_vs_core4_pct"]
    if d["p90_municipality_rmse"]<0 and d["worst_decile_mean_rmse"]<0 and d["pooled_rmse"]<=1.0:
        promising.append(gamma)

res={
 "status":"core4_geographic_equity_postprocess_challenger",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":EVAL_YEARS,
 "n_municipalities":290,
 "base_predictions":"frozen 6-year rolling-origin core4",
 "method":{
   "challenger":"shrink each municipality prediction toward forecast-year cross-sectional median prediction",
   "lambda_grid":LAMBDAS,
   "gamma_grid":GAMMAS,
   "selection_objective":"historical pooled RMSE + gamma * historical p90 municipality RMSE",
   "out_of_time_rule":"forecast year uses only earlier forecast years to select lambda",
   "no_feature_refit":True,
   "no_contemporaneous_outcome_use":True
 },
 "selection_history":selections,
 "summary":summary,
 "promising_gammas":promising,
 "decision_rule":"Promising only if p90 and worst-decile municipality RMSE improve and pooled RMSE deteriorates by no more than 1%."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
