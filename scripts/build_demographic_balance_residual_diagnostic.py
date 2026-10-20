#!/usr/bin/env python3
"""Build explicit demographic balance residual diagnostics for forecast integration.

The accounting identity is:
  delta_population = births - deaths + inflow - outflow + residual

Residual is NOT absorbed into any component model. This script characterizes
its stability and provides simple correction candidates for later forecast
integration. Production models are unchanged.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
bal=json.loads((D/"demographic_balance_historical_diagnostic.json").read_text(encoding="utf-8"))
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one").sort_values(["kommun_kod","year"])
q["pop_prev"]=q.groupby("kommun_kod")["folkmangd"].shift(1)
q["delta_population"]=q["folkmangd"]-q["pop_prev"]
q["births"]=q["fodelsetal_per_100"]*q["mean_population"]/100.0
q["deaths"]=q["dodstal_per_1000"]*q["mean_population"]/1000.0
q["component_change"]=q["births"]-q["deaths"]+q["inflyttade"]-q["utflyttade"]
q["residual"]=q["delta_population"]-q["component_change"]
q=q[q.year.between(2014,2024)].copy()

def stats(x):
    a=np.asarray(x,float)
    return {
      "n":int(len(a)),
      "mean":float(np.mean(a)),
      "median":float(np.median(a)),
      "mae_zero":float(np.mean(np.abs(a))),
      "rmse_zero":float(np.sqrt(np.mean(a*a))),
      "p95_abs":float(np.quantile(np.abs(a),0.95))
    }

out={
 "status":"demographic_balance_residual_diagnostic",
 "production_changed":False,
 "identity":"delta_population = births - deaths + inflow - outflow + residual",
 "principle":"Residual is modeled separately and is never folded into birth, death, inflow or outflow targets.",
 "all_municipalities":stats(q.residual.dropna()),
 "lulea":{"overall":stats(q[q.kommun_kod.eq("2580")].residual.dropna()),"windows":{}},
}

lu=q[q.kommun_kod.eq("2580")][["year","residual"]].dropna().copy()
for w in [3,5,10]:
    vals=lu.tail(w).residual
    out["lulea"]["windows"][str(w)]=stats(vals)
out["lulea"]["years"]=[{"year":int(r.year),"residual":float(r.residual)} for r in lu.itertuples(index=False)]

# Compare simple correction rules by one-step rolling origin for Lulea.
rules={"zero":[],"mean3":[],"median3":[]}
for y in sorted(lu.year.unique()):
    hist=lu[lu.year<y].tail(3).residual
    if len(hist)<3: continue
    actual=float(lu.loc[lu.year.eq(y),"residual"].iloc[0])
    preds={"zero":0.0,"mean3":float(hist.mean()),"median3":float(hist.median())}
    for name,pred in preds.items():
        rules[name].append(actual-pred)
out["lulea"]["rolling_correction_rules"]={}
for name,errs in rules.items():
    a=np.asarray(errs,float)
    out["lulea"]["rolling_correction_rules"][name]={
      "n_origins":int(len(a)),
      "rmse":float(np.sqrt(np.mean(a*a))),
      "mae":float(np.mean(np.abs(a))),
      "bias_actual_minus_prediction":float(np.mean(a))
    }

(D/"demographic_balance_residual_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
