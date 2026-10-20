#!/usr/bin/env python3
"""Lulea-specific rolling-origin validation for locked annual outmigration core.

Locked core:
  utflyttning_per_1000 ~ lag1_utflyttning_per_1000
  3-year rolling training window across all 290 municipalities.

Sensitivity:
  same model with 10-year rolling window.

Reports Lulea annual OOT predictions, errors, RMSE/MAE/bias, and converts
per-1000 predictions to counts when population is available in the panel.
Research validation only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
TARGET="utflyttning_per_1000"
FEATURE=["lag1_utflyttning_per_1000"]
LULEA="2580"
ALPHAS=[0.0,0.1,1.0,10.0]

for c in [TARGET]+FEATURE:
    p[c]=pd.to_numeric(p[c],errors="coerce")

# pick best available population column for count conversion
pop_candidates=["folkmangd","population","befolkning","invånare","invanare"]
POP=next((c for c in pop_candidates if c in p.columns),None)
if POP:
    p[POP]=pd.to_numeric(p[POP],errors="coerce")

def pipe(alpha):
    return make_pipeline(StandardScaler(),Ridge(alpha=1e-10 if alpha==0 else alpha))

def choose_alpha(train):
    yrs=sorted(train.year.unique())
    vy=yrs[-1]
    fit=train[train.year<vy]
    val=train[train.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=pipe(a);m.fit(fit[FEATURE],fit[TARGET]);pr=m.predict(val[FEATURE])
        e=val[TARGET].to_numpy(float)-pr
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return sorted(scores,key=lambda z:(z[0],-z[1]))[0][1]

def run(window):
    rows=[]
    first=2003+window
    for fy in range(first,2025):
        train_years=list(range(fy-window,fy))
        tr=p[p.year.isin(train_years)].dropna(subset=[TARGET]+FEATURE).copy()
        te=p[(p.year.eq(fy)) & (p.kommun_kod.eq(LULEA))].dropna(subset=[TARGET]+FEATURE).copy()
        if len(tr)!=290*window or len(te)!=1:
            continue
        alpha=choose_alpha(tr)
        m=pipe(alpha);m.fit(tr[FEATURE],tr[TARGET])
        pred=float(m.predict(te[FEATURE])[0])
        actual=float(te[TARGET].iloc[0])
        row={"year":int(fy),"actual_per_1000":actual,"prediction_per_1000":pred,
             "error_prediction_minus_actual":pred-actual,"alpha":alpha}
        if POP and pd.notna(te[POP].iloc[0]):
            pop=float(te[POP].iloc[0])
            row["population"]=pop
            row["actual_count"]=actual*pop/1000.0
            row["prediction_count"]=pred*pop/1000.0
            row["error_count_prediction_minus_actual"]=row["prediction_count"]-row["actual_count"]
        rows.append(row)
    e=np.array([r["error_prediction_minus_actual"] for r in rows],float)
    return {"window_years":window,"n_years":len(rows),
            "rmse_per_1000":float(np.sqrt(np.mean(e*e))),
            "mae_per_1000":float(np.mean(np.abs(e))),
            "bias_prediction_minus_actual":float(np.mean(e)),
            "years_better_than_zero_error_within_1_per_1000":int(np.sum(np.abs(e)<=1)),
            "rows":rows}

res3=run(3);res10=run(10)
common=sorted(set(r["year"] for r in res3["rows"]) & set(r["year"] for r in res10["rows"]))
r3={r["year"]:r for r in res3["rows"]};r10={r["year"]:r for r in res10["rows"]}
wins3=wins10=0
for y in common:
    a=abs(r3[y]["error_prediction_minus_actual"])
    b=abs(r10[y]["error_prediction_minus_actual"])
    if a<b:wins3+=1
    elif b<a:wins10+=1

out={"status":"outmigration_lulea_locked_core_validation",
     "production_changed":False,"inflow_model_changed":False,
     "municipality":"Luleå","kommunkod":LULEA,
     "target":TARGET,"feature":FEATURE[0],
     "population_column_for_counts":POP,
     "core_3y":res3,"sensitivity_10y":res10,
     "common_year_comparison":{"years":common,"3y_abs_error_wins":wins3,
                               "10y_abs_error_wins":wins10,
                               "ties":len(common)-wins3-wins10}}
(D/"outmigration_lulea_locked_core_validation.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
