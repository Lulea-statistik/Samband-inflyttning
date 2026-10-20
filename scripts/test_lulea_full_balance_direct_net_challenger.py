#!/usr/bin/env python3
"""Compare current full component backtest with direct net-migration challenger.

Challenger:
- direct net migration per 1000
- predictors: lag1 inflow per 1000 + lag1 outflow per 1000
- 10-year national rolling training
- same birth, death, residual and Y-1 exposure as current full component backtest

Research diagnostic only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p.sort_values(["kommun_kod","year"])
p["net_migration_per_1000"]=p["inflyttning_per_1000"]-p["utflyttning_per_1000"]

base=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
FEATURES=["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"]
ALPHAS=[0.0,0.1,1.0,10.0]

def model(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         Ridge(alpha=1e-10 if a==0 else a))

def choose_alpha(tr):
    yrs=sorted(int(x) for x in tr.year.unique())
    vy=yrs[-1]
    fit=tr[tr.year<vy]; val=tr[tr.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=model(a).fit(fit[FEATURES],fit["net_migration_per_1000"])
        pred=m.predict(val[FEATURES])
        e=pred-val["net_migration_per_1000"].to_numpy(float)
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return min(scores,key=lambda x:(x[0],-x[1]))[1]

rows=[]
for b in base["years"]:
    y=int(b["year"])
    lu=p[(p.year.eq(y))&(p.kommun_kod.eq("2580"))]
    tr=p[p.year.isin(range(y-10,y))].dropna(subset=FEATURES+["net_migration_per_1000"]).copy()
    if len(lu)!=1 or len(tr)!=2900: continue
    a=choose_alpha(tr)
    m=model(a).fit(tr[FEATURES],tr["net_migration_per_1000"])
    net_rate=float(m.predict(lu[FEATURES])[0])
    net_persons=net_rate*float(b["population_prev"])/1000.0
    pred_change_direct=float(b["births_pred"])-float(b["deaths_pred"])+net_persons+float(b["residual_pred"])
    actual=float(b["actual_change"])
    rows.append({
      "year":y,
      "actual_change":actual,
      "baseline_pred_change":float(b["pred_change"]),
      "baseline_error_actual_minus_prediction":float(b["error_actual_minus_prediction"]),
      "direct_net_rate_pred":net_rate,
      "direct_net_persons_pred":net_persons,
      "direct_net_alpha":a,
      "direct_pred_change":pred_change_direct,
      "direct_error_actual_minus_prediction":actual-pred_change_direct
    })

df=pd.DataFrame(rows)
def metrics(x):
    a=np.asarray(x,float)
    return {"n":int(len(a)),
            "rmse_persons":float(np.sqrt(np.mean(a*a))),
            "mae_persons":float(np.mean(np.abs(a))),
            "bias_actual_minus_prediction":float(np.mean(a))}
out={
 "status":"lulea_full_balance_direct_net_challenger",
 "production_changed":False,
 "challenger":{
   "target":"net_migration_per_1000",
   "features":FEATURES,
   "window_years":10,
   "training":"national rolling",
   "rate_to_count_exposure":"population at Y-1"
 },
 "baseline":metrics(df.baseline_error_actual_minus_prediction),
 "direct_net":metrics(df.direct_error_actual_minus_prediction),
 "rmse_improvement_pct":float(
   100*(metrics(df.baseline_error_actual_minus_prediction)["rmse_persons"]-
        metrics(df.direct_error_actual_minus_prediction)["rmse_persons"])/
       metrics(df.baseline_error_actual_minus_prediction)["rmse_persons"]
 ),
 "mae_improvement_pct":float(
   100*(metrics(df.baseline_error_actual_minus_prediction)["mae_persons"]-
        metrics(df.direct_error_actual_minus_prediction)["mae_persons"])/
       metrics(df.baseline_error_actual_minus_prediction)["mae_persons"]
 ),
 "years":rows
}
(D/"lulea_full_balance_direct_net_challenger.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
