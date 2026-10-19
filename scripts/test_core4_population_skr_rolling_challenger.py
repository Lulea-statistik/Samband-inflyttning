#!/usr/bin/env python3
"""Rolling-origin challenger: population reliability blend + shrunk SKR residual.

Research only. No structural core4 changes.

Evaluation 2020-2024 because SKR correction at year t uses only residuals from years < t.
Inputs:
- historical six-year rolling core4 predictions
- panel.csv for lag1 population + lag1 persistence
- fixed SKR 2023 mapping produced by prior diagnostic

Arms:
A core4
B population reliability blend, fixed C=10000
C population reliability blend + shrunk SKR residual correction

SKR correction at forecast year t:
- use residuals of arm B from prior evaluation years only
- residual = prediction - actual
- group_mean_prior = mean residual within SKR group, years < t
- shrink factor n/(n+K), K fixed at 30 before test
- corrected prediction = armB - shrink*group_mean_prior

No tuning. K=30 is fixed ad hoc for this research test and must not be tuned on the same results.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
P=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
PANEL=D/"panel.csv"
SKR=D/"geographic_bias_sources/skr_kommungrupp_2023.csv"
OUT=D/"three_year_forecast_core4_population_skr_rolling_challenger.json"
OUTCSV=D/"three_year_forecast_core4_population_skr_rolling_challenger_predictions.csv"

YEARS=list(range(2019,2025))
EVAL=list(range(2020,2025))
C=10000.0
K=30.0

p=pd.read_csv(P,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[(p["window_years"].eq(6)) & p["forecast_year"].isin(YEARS)].copy()
p=p.rename(columns={"forecast_year":"year"})

panel=pd.read_csv(PANEL,dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
need=["kommun_kod","year","lag1_log_folkmangd","lag1_inflyttning_per_1000"]
panel=panel[need].copy()
panel["lag1_log_folkmangd"]=pd.to_numeric(panel["lag1_log_folkmangd"],errors="coerce")
panel["lag1_inflyttning_per_1000"]=pd.to_numeric(panel["lag1_inflyttning_per_1000"],errors="coerce")

skr=pd.read_csv(SKR,dtype={"kommun_kod":str})
skr["kommun_kod"]=skr["kommun_kod"].astype(str).str.zfill(4)

p=p.merge(panel,on=["kommun_kod","year"],how="left",validate="one_to_one")
p=p.merge(skr[["kommun_kod","skr_group","skr_group_name"]],on="kommun_kod",how="left",validate="many_to_one")
if p[["lag1_log_folkmangd","lag1_inflyttning_per_1000","skr_group"]].isna().any().any():
    raise SystemExit("Missing population/persistence/SKR fields")

p["population"]=np.exp(p["lag1_log_folkmangd"])
p["core4"]=p["prediction"]
p["core4_weight"]=p["population"]/(p["population"]+C)
p["population_blend"]=p["core4_weight"]*p["core4"]+(1-p["core4_weight"])*p["lag1_inflyttning_per_1000"]
p["population_blend_residual"]=p["population_blend"]-p["actual"]

# Strict rolling SKR correction
p["skr_prior_n"]=0
p["skr_prior_mean_residual"]=0.0
p["skr_shrink"]=0.0
p["population_skr_blend"]=np.nan

for y in YEARS:
    cur=p["year"].eq(y)
    if y==min(YEARS):
        p.loc[cur,"population_skr_blend"]=p.loc[cur,"population_blend"]
        continue
    prior=p[p["year"]<y].copy()
    stats=prior.groupby("skr_group")["population_blend_residual"].agg(["count","mean"])
    for grp,idx in p[cur].groupby("skr_group").groups.items():
        if grp in stats.index:
            n=float(stats.loc[grp,"count"])
            m=float(stats.loc[grp,"mean"])
            sh=n/(n+K)
        else:
            n=0.0; m=0.0; sh=0.0
        p.loc[idx,"skr_prior_n"]=n
        p.loc[idx,"skr_prior_mean_residual"]=m
        p.loc[idx,"skr_shrink"]=sh
        p.loc[idx,"population_skr_blend"]=p.loc[idx,"population_blend"]-sh*m

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

ev=p[p["year"].isin(EVAL)].copy()
summary={k:met(ev,k) for k in ["core4","population_blend","population_skr_blend"]}
for arm in ["population_blend","population_skr_blend"]:
    summary[arm]["rmse_change_vs_core4_pct"]=100*(summary[arm]["rmse"]/summary["core4"]["rmse"]-1)
    summary[arm]["p95_change_vs_core4_pct"]=100*(summary[arm]["p95_absolute_error"]/summary["core4"]["p95_absolute_error"]-1)
summary["population_skr_blend"]["rmse_change_vs_population_blend_pct"]=100*(summary["population_skr_blend"]["rmse"]/summary["population_blend"]["rmse"]-1)
summary["population_skr_blend"]["p95_change_vs_population_blend_pct"]=100*(summary["population_skr_blend"]["p95_absolute_error"]/summary["population_blend"]["p95_absolute_error"]-1)

yearly=[]
for y,g in ev.groupby("year"):
    rec={"year":int(y)}
    for arm in ["core4","population_blend","population_skr_blend"]:
        rec[arm]=met(g,arm)
    rec["skr_vs_population_rmse_pct"]=100*(rec["population_skr_blend"]["rmse"]/rec["population_blend"]["rmse"]-1)
    rec["skr_vs_population_p95_pct"]=100*(rec["population_skr_blend"]["p95_absolute_error"]/rec["population_blend"]["p95_absolute_error"]-1)
    yearly.append(rec)

by_skr=[]
for grp,g in ev.groupby(["skr_group","skr_group_name"]):
    code,name=grp
    by_skr.append({
      "skr_group":code,"skr_group_name":name,
      "core4":met(g,"core4"),
      "population_blend":met(g,"population_blend"),
      "population_skr_blend":met(g,"population_skr_blend")
    })

l=ev[ev["kommun_kod"].eq("2580")].copy()
lulea={
 "core4_mae":met(l,"core4")["mae"],
 "population_blend_mae":met(l,"population_blend")["mae"],
 "population_skr_blend_mae":met(l,"population_skr_blend")["mae"],
 "annual":[
   {"year":int(r.year),"actual":float(r.actual),"core4":float(r.core4),
    "population_blend":float(r.population_blend),"population_skr_blend":float(r.population_skr_blend),
    "skr_prior_mean_residual":float(r.skr_prior_mean_residual),"skr_shrink":float(r.skr_shrink)}
   for _,r in l.iterrows()
 ]
}

result={
 "status":"core4_population_skr_rolling_challenger",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "design":{
   "evaluation_years":EVAL,
   "population_C_fixed":C,
   "skr_shrink_K_fixed":K,
   "skr_correction_uses_only_prior_years":True,
   "parameter_tuning":False
 },
 "summary":summary,
 "yearly":yearly,
 "by_skr_group":sorted(by_skr,key=lambda x:x["skr_group"]),
 "lulea":lulea,
 "decision_rule":"Research challenger only. Promising only if it improves on population blend overall RMSE and upper-tail errors without unstable year/group deterioration.",
 "guardrail":"K=30 is fixed for this test and must not be tuned on these same retrospective results."
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
p.to_csv(OUTCSV,index=False)
print(json.dumps({"summary":summary,"yearly":yearly,"lulea":lulea},ensure_ascii=False,indent=2))
