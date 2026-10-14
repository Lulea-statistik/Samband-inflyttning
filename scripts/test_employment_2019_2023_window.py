#!/usr/bin/env python3
"""Fixed 2019-2023 training -> 2024 exploratory diagnostic, transparent 2020 gap."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
D=Path("docs/data")
TARGET=json.loads((D/"model.json").read_text(encoding="utf-8"))["target"]
BASE=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
MODELS={"baseline":BASE,"residence":BASE+["residence","residence_missing"],
 "workplace":BASE+["workplace","workplace_missing"],
 "both":BASE+["residence","residence_missing","workplace","workplace_missing"]}
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p.kommun_kod=p.kommun_kod.str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag.kommun_kod=lag.kommun_kod.str.zfill(4)
assert not lag.duplicated(["target_year","kommun_kod","dimension"]).any()
wide=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index()
wide=wide.rename(columns={"target_year":"year"})
d=p.loc[p.year.between(2019,2024),["year","kommun_kod",TARGET]+BASE].merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one")
for c in [TARGET]+BASE+["residence","workplace"]:d[c]=pd.to_numeric(d[c],errors="coerce")
if d.duplicated(["year","kommun_kod"]).any():raise RuntimeError("Panel duplicate")
if len(d)!=6*290 or any(d.groupby("year").size()!=290):raise RuntimeError("Incomplete years")
if d[[TARGET]+BASE].isna().any().any():raise RuntimeError("Missing baseline values")
if d.loc[d.year==2020,["residence","workplace"]].notna().any().any():raise RuntimeError("2020 method break unexpectedly populated")
for c in ["residence","workplace"]:
    missing=d[c].isna()
    if d.loc[d.year!=2020,c].isna().any():raise RuntimeError("Other growth values missing")
    d[c+"_missing"]=missing.astype(int)
    # Missing 2020 source value is encoded via missingness marker, not an observed growth value.
    train_values=d.loc[(d.year<=2023)&(d.year!=2020),c].dropna()
    fill=float(train_values.median())
    d[c]=d[c].fillna(fill)
train=d[d.year<=2023].copy()
test=d[d.year==2024].copy()
if len(train)!=1450 or len(test)!=290:raise RuntimeError("Sample size mismatch")
output={"status":"exploratory_2019_2023_train_2024_test","n_train":1450,"n_test":290,
  "method_gap_year":2020,"missingness_handling":"training-median fill with explicit gap indicator, never an observed year-on-year growth",
  "models":MODELS,"ridge_alpha":10.,"results":{},"production_changed":False,
  "limitations":["2024 is a repeatedly inspected outcome, not independent confirmation.",
    "The 2020 method break remains unresolved; median imputation is only a transparent statistical device.",
    "Predictor vintages are retrospective, not verified as available in real time.",
    "This minimal structural baseline is not the complete existing production model.",
    "The gap indicator is collinear with year 2020 and may capture other time effects."]}
for name,cols in MODELS.items():
    model=make_pipeline(StandardScaler(),Ridge(alpha=10))
    model.fit(train[cols],train[TARGET])
    pred=model.predict(test[cols])
    err=test[TARGET].to_numpy()-pred
    i=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
    output["results"][name]={"rmse":float(np.sqrt(np.mean(err**2))),
      "mae":float(np.mean(abs(err))),
      "lulea_actual":float(test.iloc[i[0]][TARGET]),"lulea_pred":float(pred[i[0]])}
(D/"employment_2019_2023_fixed_window_2024.json").write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"rmse":{k:round(v["rmse"],3) for k,v in output["results"].items()}},ensure_ascii=False))
