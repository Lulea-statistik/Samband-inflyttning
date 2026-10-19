#!/usr/bin/env python3
"""Out-of-time municipality-level residual shrinkage for frozen core-4.

Research-only. Structural core-4 is unchanged.

For each forecast year y in 2020-2024:
- use only the same municipality's core-4 residuals from prior forecast years;
- estimate persistent local bias as the historical mean residual;
- shrink that estimate toward zero with n/(n+5);
- adjusted prediction = core4 prediction - shrunk residual.

No tuning, no feature selection, no contemporaneous outcome use.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
P=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
OUT=D/"three_year_forecast_core4_municipality_residual_shrinkage.json"
OUTCSV=D/"three_year_forecast_core4_municipality_residual_shrinkage_predictions.csv"
K=5.0
EVAL_YEARS=list(range(2020,2025))

p=pd.read_csv(P,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[p["window_years"].eq(6)].copy().rename(columns={"forecast_year":"year"})
if p.groupby("year")["kommun_kod"].nunique().min()!=290:
    raise SystemExit("Incomplete six-year rolling-origin prediction panel")

def metrics(actual,pred):
    e=np.asarray(pred)-np.asarray(actual)
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

rows=[]
details=[]
for y in EVAL_YEARS:
    hist=p[p["year"]<y].copy()
    te=p[p["year"].eq(y)].copy()
    stats=(hist.groupby("kommun_kod")["residual_prediction_minus_actual"]
             .agg(["mean","count","std"]).reset_index())
    stats["shrink_weight"]=stats["count"]/(stats["count"]+K)
    stats["shrunk_residual"]=stats["mean"]*stats["shrink_weight"]
    te=te.merge(stats[["kommun_kod","mean","count","std","shrink_weight","shrunk_residual"]],
                on="kommun_kod",how="left",validate="one_to_one")
    if te["shrunk_residual"].isna().any():
        raise SystemExit(f"Missing municipality residual history for {y}")
    te["core4"]=te["prediction"]
    te["municipality_shrinkage"]=te["prediction"]-te["shrunk_residual"]
    for _,r in te.iterrows():
        rows.append({
          "year":int(y),"kommun_kod":r["kommun_kod"],"actual":float(r["actual"]),
          "core4":float(r["core4"]),
          "municipality_shrinkage":float(r["municipality_shrinkage"]),
          "prior_residual_mean":float(r["mean"]),
          "prior_residual_n":int(r["count"]),
          "shrink_weight":float(r["shrink_weight"])
        })
    details.append({
      "year":y,
      "prior_years":sorted(map(int,hist["year"].unique())),
      "core4":metrics(te["actual"],te["core4"]),
      "municipality_shrinkage":metrics(te["actual"],te["municipality_shrinkage"])
    })

o=pd.DataFrame(rows)
o.to_csv(OUTCSV,index=False)
base=metrics(o["actual"],o["core4"])
adj=metrics(o["actual"],o["municipality_shrinkage"])
adj["rmse_change_vs_core4_pct"]=100*(adj["rmse"]/base["rmse"]-1)
adj["p95_abs_error_change_vs_core4_pct"]=100*(adj["p95_absolute_error"]/base["p95_absolute_error"]-1)
adj["max_abs_error_change_vs_core4_pct"]=100*(adj["max_absolute_error"]/base["max_absolute_error"]-1)

# Persistence diagnostic: how stable is each municipality's residual sign over scored history?
diag=(p[p["year"].between(2017,2024)]
      .groupby("kommun_kod")["residual_prediction_minus_actual"]
      .agg(["mean","std","count"]).reset_index())
diag["abs_mean"]=diag["mean"].abs()
persistent=diag.sort_values("abs_mean",ascending=False).head(20).to_dict("records")

l=o[o["kommun_kod"].eq("2580")].copy()
lulea=[]
for _,r in l.iterrows():
    lulea.append({
      "year":int(r["year"]),"actual":float(r["actual"]),
      "core4":float(r["core4"]),"core4_error":float(r["core4"]-r["actual"]),
      "municipality_shrinkage":float(r["municipality_shrinkage"]),
      "municipality_shrinkage_error":float(r["municipality_shrinkage"]-r["actual"]),
      "prior_residual_mean":float(r["prior_residual_mean"]),
      "prior_residual_n":int(r["prior_residual_n"]),
      "shrink_weight":float(r["shrink_weight"])
    })

res={
 "status":"core4_municipality_residual_shrinkage_research",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":EVAL_YEARS,
 "n_municipalities":290,
 "design":{
   "base_predictions":"6-year rolling-origin core4",
   "local_bias_definition":"same municipality mean prior prediction-minus-actual residual",
   "shrinkage":"n/(n+5)",
   "k_fixed":K,
   "out_of_time_rule":"forecast year uses only earlier residual years"
 },
 "summary":{"core4":base,"municipality_shrinkage":adj},
 "year_details":details,
 "largest_persistent_municipality_biases":persistent,
 "lulea":lulea,
 "decision_rule":"Promising only if RMSE and upper-tail error both improve on common years; no production promotion from retrospective evidence."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"summary":res["summary"],"lulea":lulea},ensure_ascii=False,indent=2))
