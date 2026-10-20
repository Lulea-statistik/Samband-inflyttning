#!/usr/bin/env python3
"""Recent-structure challenger gate for annual outmigration.

Locked reference:
  utflyttning_per_1000 ~ lag1_utflyttning_per_1000, 3-year rolling training.

Sensitivity reference:
  same lag1-only model, 10-year rolling training.

Recent-only candidates are evaluated only where all candidate features have a
complete 290-municipality history: forecast origins 2022, 2023, 2024, each with
a 3-year training window. No candidate gets credit from a single holdout year.
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
BASE=["lag1_utflyttning_per_1000"]
MODELS={
 "core_3y":BASE,
 "age_fritid":[*BASE,"lag1_andel_20_34","lag1_log_fritidshus_per_1000_inv"],
 "age_structure":[*BASE,"lag1_andel_20_34","lag1_log_folkmangd","lag1_log_fritidshus_per_1000_inv"],
 "fritid_only":[*BASE,"lag1_log_fritidshus_per_1000_inv"],
 "structure":[*BASE,"lag1_log_folkmangd","lag1_log_fritidshus_per_1000_inv"],
 "brott":[*BASE,"lag1_brott_per_100000"],
 "fardigstallda":[*BASE,"lag1_fardigstallda_bostader_per_1000"],
}
ALPHAS=[0.0,0.1,1.0,10.0]
FORECAST_YEARS=[2022,2023,2024]

for c in sorted(set([TARGET]+sum(MODELS.values(),[]))):
    if c not in p: raise RuntimeError(f"Missing {c}")
    p[c]=pd.to_numeric(p[c],errors="coerce")

def pipe(alpha):
    return make_pipeline(StandardScaler(),Ridge(alpha=1e-10 if alpha==0 else alpha))

def choose_alpha(train,features):
    yrs=sorted(train.year.unique())
    if len(yrs)<3:return 0.0
    vy=yrs[-1]
    fit=train[train.year<vy]
    val=train[train.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=pipe(a);m.fit(fit[features],fit[TARGET]);pr=m.predict(val[features])
        e=val[TARGET].to_numpy(float)-pr
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return sorted(scores,key=lambda z:(z[0],-z[1]))[0][1]

def fit_predict(train_years,test_year,features):
    tr=p[p.year.isin(train_years)].dropna(subset=[TARGET]+features).copy()
    te=p[p.year.eq(test_year)].dropna(subset=[TARGET]+features).copy()
    if len(tr)!=290*len(train_years) or len(te)!=290:
        raise RuntimeError(f"Incomplete panel for {features} {test_year}: {len(tr)} {len(te)}")
    alpha=choose_alpha(tr,features)
    m=pipe(alpha);m.fit(tr[features],tr[TARGET]);pred=m.predict(te[features])
    out=te[["year","kommun_kod",TARGET]].copy()
    out["prediction"]=pred
    out["error"]=pred-out[TARGET].to_numpy(float)
    out["alpha"]=alpha
    return out

def metrics(g):
    e=g.error.to_numpy(float)
    return {"n":int(len(g)),"rmse":float(np.sqrt(np.mean(e*e))),
            "mae":float(np.mean(np.abs(e))),"bias":float(np.mean(e))}

preds=[]
for fy in FORECAST_YEARS:
    train3=list(range(fy-3,fy))
    for name,features in MODELS.items():
        g=fit_predict(train3,fy,features)
        g["model"]=name;g["window"]=3
        preds.append(g)
    # 10y sensitivity reference does not need recent-only features.
    g=fit_predict(list(range(fy-10,fy)),fy,BASE)
    g["model"]="reference_10y";g["window"]=10
    preds.append(g)

o=pd.concat(preds,ignore_index=True)

res={"status":"outmigration_recent_structure_challenger_gate",
     "production_changed":False,"inflow_model_changed":False,
     "locked_reference":"core_3y",
     "sensitivity_reference":"reference_10y",
     "forecast_years":FORECAST_YEARS,
     "models":{}}

for name,g in o.groupby("model"):
    d={"overall":metrics(g),"yearly":[]}
    for fy,z in g.groupby("year"):
        q=metrics(z);q["year"]=int(fy);d["yearly"].append(q)
    res["models"][name]=d

b3=res["models"]["core_3y"]["overall"]
b10=res["models"]["reference_10y"]["overall"]
for name,d in res["models"].items():
    d["delta_rmse_pct_vs_core3"]=100*(d["overall"]["rmse"]/b3["rmse"]-1)
    d["delta_mae_pct_vs_core3"]=100*(d["overall"]["mae"]/b3["mae"]-1)
    d["delta_rmse_pct_vs_ref10"]=100*(d["overall"]["rmse"]/b10["rmse"]-1)
    if name not in ["core_3y","reference_10y"]:
        base3={x["year"]:x["rmse"] for x in res["models"]["core_3y"]["yearly"]}
        base10={x["year"]:x["rmse"] for x in res["models"]["reference_10y"]["yearly"]}
        wins3=wins10=0
        deltas3=[];deltas10=[]
        for x in d["yearly"]:
            y=x["year"]
            a=100*(x["rmse"]/base3[y]-1);c=100*(x["rmse"]/base10[y]-1)
            deltas3.append(a);deltas10.append(c)
            wins3+=a<0; wins10+=c<0
        d["stability"]={
          "wins_vs_core3":int(wins3),"wins_vs_ref10":int(wins10),
          "worst_year_delta_rmse_pct_vs_core3":float(max(deltas3)),
          "worst_year_delta_rmse_pct_vs_ref10":float(max(deltas10)),
          "median_year_delta_rmse_pct_vs_core3":float(np.median(deltas3))
        }
        # Conservative gate: improve pooled RMSE vs both references,
        # win >=2/3 years vs core3, and never be >2% worse than core3 in a year.
        d["passes_gate"]=bool(
          d["delta_rmse_pct_vs_core3"]<0 and
          d["delta_rmse_pct_vs_ref10"]<0 and
          wins3>=2 and
          max(deltas3)<=2.0
        )

challengers=[n for n in MODELS if n!="core_3y"]
res["passing_challengers"]=[n for n in challengers if res["models"][n].get("passes_gate")]
res["ranking"]=sorted(challengers,key=lambda n:(
    not res["models"][n].get("passes_gate",False),
    res["models"][n]["delta_rmse_pct_vs_core3"],
    len(MODELS[n])
))

(D/"outmigration_recent_structure_challenger_gate.json").write_text(
 json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
o.to_csv(D/"outmigration_recent_structure_challenger_predictions.csv",index=False)
print(json.dumps(res,ensure_ascii=False,indent=2))
