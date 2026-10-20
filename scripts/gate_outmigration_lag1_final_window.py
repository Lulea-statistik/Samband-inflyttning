#!/usr/bin/env python3
"""Final 3y vs 10y training-window gate for lag1-only outmigration core.

Decision principle:
- compare identical 2013-2024 forecast years and 290 municipalities;
- pooled RMSE difference smaller than 0.5% is treated as practically equivalent;
- among practically equivalent windows, prefer better year-by-year consistency;
- report municipality-level paired bootstrap of squared-error difference.

Research gate only. No production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
p=pd.read_csv(D/"outmigration_long_history_rolling_origin_predictions.csv",
              dtype={"kommun_kod":str})
p=p[(p.model=="lag1_only") & p.window.isin([3,10]) & p.forecast_year.between(2013,2024)].copy()

# Exact common panel check
for w in [3,10]:
    q=p[p.window.eq(w)]
    if len(q)!=12*290:
        raise RuntimeError(f"window {w}: expected 3480 rows, got {len(q)}")

wide=(p.pivot(index=["forecast_year","kommun_kod"],columns="window",values="error")
        .reset_index())
wide.columns=["forecast_year","kommun_kod","err3","err10"]
if len(wide)!=12*290 or wide[["err3","err10"]].isna().any().any():
    raise RuntimeError("Incomplete paired panel")

def metrics(e):
    e=np.asarray(e,float)
    return {"rmse":float(np.sqrt(np.mean(e*e))),
            "mae":float(np.mean(np.abs(e))),
            "bias":float(np.mean(e))}

m3=metrics(wide.err3)
m10=metrics(wide.err10)
delta_rmse_pct=100*(m3["rmse"]/m10["rmse"]-1)

# Year-by-year
yearly=[]
wins3=wins10=0
regret3=[];regret10=[]
for y,g in wide.groupby("forecast_year"):
    a=metrics(g.err3); b=metrics(g.err10)
    d=100*(a["rmse"]/b["rmse"]-1)
    if d<0: wins3+=1
    elif d>0: wins10+=1
    regret3.append(max(0,d))
    regret10.append(max(0,-d))
    yearly.append({"year":int(y),"rmse_3y":a["rmse"],"rmse_10y":b["rmse"],
                   "delta_3y_vs_10y_pct":float(d)})

# Paired municipality bootstrap: sample municipalities with replacement,
# retain all years for sampled municipalities.
rng=np.random.default_rng(20261020)
munis=np.array(sorted(wide.kommun_kod.unique()))
boot=[]
for _ in range(5000):
    sample=rng.choice(munis,size=len(munis),replace=True)
    parts=[wide[wide.kommun_kod.eq(m)] for m in sample]
    g=pd.concat(parts,ignore_index=True)
    r3=np.sqrt(np.mean(np.square(g.err3.to_numpy(float))))
    r10=np.sqrt(np.mean(np.square(g.err10.to_numpy(float))))
    boot.append(100*(r3/r10-1))
boot=np.array(boot)

practical_margin_pct=0.5
practically_equivalent=abs(delta_rmse_pct)<=practical_margin_pct

# Conservative consistency rule: if equivalent, prefer window with more yearly wins;
# tie-break lower mean positive regret, then lower pooled RMSE.
if practically_equivalent:
    if wins3>wins10:
        selected=3
    elif wins10>wins3:
        selected=10
    else:
        mr3=float(np.mean(regret3)); mr10=float(np.mean(regret10))
        selected=3 if mr3<mr10 else 10
else:
    selected=3 if m3["rmse"]<m10["rmse"] else 10

out={
 "status":"outmigration_lag1_final_window_gate",
 "production_changed":False,
 "model":"lag1_utflyttning_per_1000 only",
 "common_years":list(range(2013,2025)),
 "metrics":{"3y":m3,"10y":m10},
 "delta_rmse_3y_vs_10y_pct":float(delta_rmse_pct),
 "practical_equivalence_margin_pct":practical_margin_pct,
 "practically_equivalent":bool(practically_equivalent),
 "yearly":yearly,
 "year_wins":{"3y":wins3,"10y":wins10,"ties":12-wins3-wins10},
 "mean_positive_regret_pct":{"3y":float(np.mean(regret3)),"10y":float(np.mean(regret10))},
 "paired_municipality_bootstrap_delta_rmse_pct":{
   "median":float(np.median(boot)),
   "p025":float(np.quantile(boot,.025)),
   "p975":float(np.quantile(boot,.975)),
   "probability_3y_better":float(np.mean(boot<0))
 },
 "selected_window_years":selected,
 "decision_rule":"If pooled RMSE differs by <=0.5%, treat as practically equivalent and prefer the window with more year-by-year wins.",
 "decision":"Use selected window as the long-history lag1-only outmigration core; keep the other as sensitivity reference."
}
(D/"outmigration_lag1_final_window_gate.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
