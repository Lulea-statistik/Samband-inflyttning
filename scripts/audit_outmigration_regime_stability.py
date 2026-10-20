#!/usr/bin/env python3
"""Regime stability audit for compact outmigration core.

Compare lag1-only vs lag1+age20_34 across older/newer historical regimes and
multiple rolling training windows. The purpose is to avoid selecting a model
because of a narrow recent period.

Research only. No production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
p=pd.read_csv(D/"outmigration_long_history_rolling_origin_predictions.csv",
              dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)

MODELS=["lag1_only","lag1_plus_age20_34"]
WINDOWS=[3,5,6,10]
REGIMES={
 "early":[2006,2007,2008,2009,2010,2011,2012,2013,2014],
 "late":[2015,2016,2017,2018,2019,2020,2021,2022,2023,2024],
 "pre2020":[2006,2007,2008,2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019],
 "2020plus":[2020,2021,2022,2023,2024]
}

def m(g):
    e=g.error.to_numpy(float)
    return {
      "n":int(len(g)),
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(np.abs(e))),
      "bias_prediction_minus_actual":float(np.mean(e))
    }

out={"status":"outmigration_regime_stability_audit",
     "production_changed":False,
     "models":MODELS,"windows":WINDOWS,"regimes":REGIMES,
     "results":{}}

for w in WINDOWS:
    q=p[p.window.eq(w)]
    wr={}
    for rname,years in REGIMES.items():
        z=q[q.forecast_year.isin(years)]
        if z.empty: continue
        block={}
        for model in MODELS:
            g=z[z.model.eq(model)]
            if not g.empty:block[model]=m(g)
        if set(MODELS).issubset(block):
            b=block["lag1_only"]; c=block["lag1_plus_age20_34"]
            block["delta_age20_34_vs_lag1_only_pct"]={
              "rmse":100*(c["rmse"]/b["rmse"]-1),
              "mae":100*(c["mae"]/b["mae"]-1)
            }
        wr[rname]=block
    # year-by-year win/loss severity
    base=q[q.model.eq("lag1_only")].groupby("forecast_year").apply(
        lambda g: float(np.sqrt(np.mean(np.square(g.error.to_numpy(float))))),include_groups=False)
    chal=q[q.model.eq("lag1_plus_age20_34")].groupby("forecast_year").apply(
        lambda g: float(np.sqrt(np.mean(np.square(g.error.to_numpy(float))))),include_groups=False)
    common=sorted(set(base.index)&set(chal.index))
    deltas=[100*(chal[y]/base[y]-1) for y in common]
    wr["year_stability"]={
      "forecast_years":[int(y) for y in common],
      "wins":int(sum(d<0 for d in deltas)),
      "losses":int(sum(d>0 for d in deltas)),
      "share_better":float(np.mean(np.array(deltas)<0)),
      "median_delta_rmse_pct":float(np.median(deltas)),
      "p75_delta_rmse_pct":float(np.quantile(deltas,.75)),
      "worst_delta_rmse_pct":float(np.max(deltas)),
      "best_delta_rmse_pct":float(np.min(deltas))
    }
    out["results"][str(w)]=wr

# Conservative gate: challenger must improve every broad regime on RMSE and
# improve at least 60% of years in both 6y and 10y windows.
regime_ok=True
for w in ["6","10"]:
    for r in ["early","late","pre2020","2020plus"]:
        x=out["results"].get(w,{}).get(r,{}).get("delta_age20_34_vs_lag1_only_pct")
        if x is None: continue
        if x["rmse"]>=0: regime_ok=False
share_ok=all(out["results"][w]["year_stability"]["share_better"]>=0.60 for w in ["6","10"])
out["gate"]={
 "regime_rmse_improves_where_available":bool(regime_ok),
 "share_years_better_6y_and_10y_ge_60pct":bool(share_ok),
 "passes":bool(regime_ok and share_ok),
 "decision":"Promote age20_34 only if both conditions pass; otherwise keep lag1-only as long-history core."
}

(D/"outmigration_regime_stability_audit.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
