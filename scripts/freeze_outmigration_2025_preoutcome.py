#!/usr/bin/env python3
"""Freeze untouched 2025 outmigration predictions before SCB outcome exists.

Promoted specification:
  25% lag1-only model trained on 2022-2024
  75% lag1-only model trained on 2015-2024

Feature:
  lag1_utflyttning_per_1000 = observed 2024 utflyttning_per_1000

The script uses only data through 2024. It does not query or read any 2025
outmigration outcome. Outputs are hashed so the future 2025 scoring can verify
that predictions were genuinely frozen pre-outcome.
"""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
OUT=D/"preoutcome_2025_outmigration"
OUT.mkdir(parents=True,exist_ok=True)

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
for c in ["utflyttning_per_1000","lag1_utflyttning_per_1000","year"]:
    p[c]=pd.to_numeric(p[c],errors="coerce")

FEATURE=["lag1_utflyttning_per_1000"]
TARGET="utflyttning_per_1000"
ALPHAS=[0.0,0.1,1.0,10.0]

def model(alpha):
    return make_pipeline(StandardScaler(),Ridge(alpha=1e-10 if alpha==0 else alpha))

def choose_alpha(train):
    yrs=sorted(int(x) for x in train.year.unique())
    vy=yrs[-1]
    fit=train[train.year<vy]
    val=train[train.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=model(a);m.fit(fit[FEATURE],fit[TARGET]);pred=m.predict(val[FEATURE])
        e=pred-val[TARGET].to_numpy(float)
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return sorted(scores,key=lambda x:(x[0],-x[1]))[0][1]

def fit_component(train_years,label):
    tr=p[p.year.isin(train_years)].dropna(subset=FEATURE+[TARGET]).copy()
    if len(tr)!=290*len(train_years):
        raise SystemExit(f"{label}: expected {290*len(train_years)} train rows, got {len(tr)}")
    alpha=choose_alpha(tr)
    m=model(alpha);m.fit(tr[FEATURE],tr[TARGET])
    return m,alpha,tr

# 2025 lag1 predictor comes mechanically from final 2024 outcome.
base2024=p[p.year.eq(2024)][["kommun_kod","utflyttning_per_1000"]].dropna().copy()
if len(base2024)!=290 or base2024.kommun_kod.nunique()!=290:
    raise SystemExit(f"Expected 290 municipalities in 2024, got {len(base2024)}")
x2025=base2024.rename(columns={"utflyttning_per_1000":"lag1_utflyttning_per_1000"})
x2025["forecast_year"]=2025

m3,a3,tr3=fit_component([2022,2023,2024],"3y")
m10,a10,tr10=fit_component(list(range(2015,2025)),"10y")

pred3=m3.predict(x2025[FEATURE])
pred10=m10.predict(x2025[FEATURE])
out=x2025.copy()
out["forecast_3y_per_1000"]=pred3
out["forecast_10y_per_1000"]=pred10
out["forecast_blend_25_75_per_1000"]=0.25*pred3+0.75*pred10
out["alpha_3y"]=a3
out["alpha_10y"]=a10
out=out.sort_values("kommun_kod")

pred_path=OUT/"predictions_2025.csv"
x_path=OUT/"predictor_matrix_2025.csv"
tr3_path=OUT/"training_3y_2022_2024.csv"
tr10_path=OUT/"training_10y_2015_2024.csv"
out.to_csv(pred_path,index=False)
x2025.to_csv(x_path,index=False)
tr3[["kommun_kod","year",TARGET]+FEATURE].to_csv(tr3_path,index=False)
tr10[["kommun_kod","year",TARGET]+FEATURE].to_csv(tr10_path,index=False)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

manifest={
 "status":"outmigration_2025_predictions_frozen_pre_outcome",
 "forecast_year":2025,
 "specification":"0.25 * lag1-only 3y + 0.75 * lag1-only 10y",
 "target":"utflyttning_per_1000",
 "feature":"lag1_utflyttning_per_1000",
 "train_years_3y":[2022,2023,2024],
 "train_years_10y":list(range(2015,2025)),
 "alpha_3y":a3,
 "alpha_10y":a10,
 "prediction_rows":int(len(out)),
 "lulea_prediction":out[out.kommun_kod.eq("2580")].to_dict("records"),
 "outcome_2025_read":False,
 "outcome_2025_queried":False,
 "refit_after_outcome":False,
 "files_sha256":{
   str(pred_path):sha(pred_path),
   str(x_path):sha(x_path),
   str(tr3_path):sha(tr3_path),
   str(tr10_path):sha(tr10_path)
 }
}
(OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
