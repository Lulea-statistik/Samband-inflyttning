#!/usr/bin/env python3
"""Decompose full Lulea population-change forecast error by component.

Uses the completed full-component backtest and observed component outcomes.
No model selection or production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
bt=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)

q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one")
lu=q[q.kommun_kod.eq("2580")].copy()
lu["pop_prev"]=lu.sort_values("year")["folkmangd"].shift(1)
lu["births_obs"]=lu["fodelsetal_per_100"]*lu["mean_population"]/100.0
lu["deaths_obs"]=lu["dodstal_per_1000"]*lu["mean_population"]/1000.0

rows=[]
for r in bt["years"]:
    y=r["year"]
    a=lu[lu.year.eq(y)]
    if len(a)!=1: continue
    a=a.iloc[0]
    comps={
      "birth": float(a.births_obs-r["births_pred"]),
      "death": float(-(a.deaths_obs-r["deaths_pred"])),
      "inflow": float(a.inflyttade-r["inflow_pred"]),
      "outflow": float(-(a.utflyttade-r["outflow_pred"])),
      "residual": float((a.folkmangd-a.pop_prev-(a.births_obs-a.deaths_obs+a.inflyttade-a.utflyttade))-r["residual_pred"])
    }
    rows.append({
      "year":int(y),
      "total_error_actual_minus_prediction":float(r["error_actual_minus_prediction"]),
      **{f"{k}_contribution":v for k,v in comps.items()},
      "reconstructed_error":float(sum(comps.values())),
      "largest_abs_component":max(comps,key=lambda k:abs(comps[k])),
      "largest_abs_component_persons":float(max(abs(v) for v in comps.values()))
    })

df=pd.DataFrame(rows)
summary={}
for c in ["birth","death","inflow","outflow","residual"]:
    x=df[f"{c}_contribution"].to_numpy(float)
    summary[c]={
      "rmse_contribution":float(np.sqrt(np.mean(x*x))),
      "mae_contribution":float(np.mean(np.abs(x))),
      "mean_contribution":float(np.mean(x)),
      "years_largest_component":int((df.largest_abs_component==c).sum())
    }

out={
 "status":"lulea_full_component_error_decomposition",
 "production_changed":False,
 "sign_convention":"positive contribution means actual population change was higher than predicted because of that component",
 "summary":summary,
 "years":rows
}
(D/"lulea_full_component_error_decomposition.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
