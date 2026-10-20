#!/usr/bin/env python3
"""Feature-count robustness for the 12-month outmigration monthly module."""
import csv,json,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F2=Path("docs/data/short_term_monthly_candidate_family_2.csv")
TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/outmigration_monthly_12m_feature_count.json")
PRED=Path("docs/data/outmigration_monthly_12m_feature_count_predictions.csv")

H=12
ALPHAS=[10.0,30.0]
MIN_TRAIN=24
EMP="bas2_age25_29_sysselsattningsgrad_yoy_pp"
LFP="bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
ARMS={
 "employment_only_lag1":{"lag":1,"features":[EMP]},
 "labour_force_only_lag1":{"lag":1,"features":[LFP]},
 "both_rates_lag1":{"lag":1,"features":[EMP,LFP]}
}

def read(p):
    with p.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x in (None,""):return None
        v=float(x);return v if math.isfinite(v) else None
    except:return None
def mi(s):return int(s[:4])*12+int(s[-2:])
def rmse(e):return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e):return sum(abs(x) for x in e)/len(e) if e else None
def bias(e):return sum(e)/len(e) if e else None
def pct(a,b):return 100*(a/b-1) if a is not None and b not in (None,0) else None

f2={r["month"]:r for r in read(F2)}
tr={r["month"]:r for r in read(TARGET)}
months=sorted(tr,key=mi)
idx={mi(m):m for m in months}

def tsum(k,shift=0):
    labs=[idx.get(k+i+shift) for i in range(1,H+1)]
    if any(x is None for x in labs):return None,None
    vals=[num(tr[x].get("all_outmigrations")) for x in labs]
    if any(v is None for v in vals):return None,None
    return sum(vals),labs[-1]

def arm_x(origin,spec):
    fm=idx.get(mi(origin)-spec["lag"])
    if fm is None:return None,None
    r=f2.get(fm)
    if not r:return None,None
    x=[num(r.get(c)) for c in spec["features"]]
    if any(v is None for v in x):return None,None
    return x,fm

base=[]
for origin in months:
    k=mi(origin)
    actual,end=tsum(k,0); seasonal,_=tsum(k,-12)
    if actual is None or seasonal is None:continue
    xs={};fms={};ok=True
    for arm,spec in ARMS.items():
        x,fm=arm_x(origin,spec)
        if x is None:ok=False;break
        xs[arm]=x;fms[arm]=fm
    if ok:
        base.append({"origin":origin,"k":k,"target_end":end,"actual":actual,
                     "seasonal":seasonal,"residual":actual-seasonal,"x":xs,"feature_months":fms})

summaries={};preds=[]
for alpha in ALPHAS:
    rows=[]
    for i,row in enumerate(base):
        train=[r for r in base[:i] if mi(r["target_end"])<=row["k"]]
        if len(train)<MIN_TRAIN:continue
        rec={"horizon_months":H,"alpha":alpha,"origin":row["origin"],"target_end":row["target_end"],
             "actual":row["actual"],"seasonal":row["seasonal"],"seasonal_error":row["seasonal"]-row["actual"]}
        for arm in ARMS:
            X=np.asarray([r["x"][arm] for r in train],float)
            y=np.asarray([r["residual"] for r in train],float)
            m=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
            m.fit(X,y)
            p=row["seasonal"]+float(m.predict(np.asarray([row["x"][arm]],float))[0])
            rec[arm]=p;rec[arm+"_error"]=p-row["actual"]
        rows.append(rec);preds.append(rec)
    se=[r["seasonal_error"] for r in rows]
    stats={"seasonal":{"rmse":rmse(se),"mae":mae(se),"bias":bias(se)}}
    for arm in ARMS:
        e=[r[arm+"_error"] for r in rows]
        stats[arm]={"rmse":rmse(e),"mae":mae(e),"bias":bias(e),
                    "delta_rmse_pct_vs_seasonal":pct(rmse(e),rmse(se)),
                    "delta_mae_pct_vs_seasonal":pct(mae(e),mae(se))}
    summaries[str(alpha)]={
      "n_origins":len(rows),
      "first_origin":rows[0]["origin"] if rows else None,
      "last_origin":rows[-1]["origin"] if rows else None,
      "ranked_by_rmse":sorted(stats,key=lambda a:stats[a]["rmse"]),
      "stats":stats,
      "single_vs_both":{
        "employment_only_delta_rmse_pct":pct(stats["employment_only_lag1"]["rmse"],stats["both_rates_lag1"]["rmse"]),
        "labour_force_only_delta_rmse_pct":pct(stats["labour_force_only_lag1"]["rmse"],stats["both_rates_lag1"]["rmse"])
      }
    }

res={"status":"outmigration_monthly_12m_feature_count",
     "generated_at_utc":datetime.now(timezone.utc).isoformat(),
     "production_changed":False,"annual_outmigration_blend_changed":False,
     "target":"all_outmigrations","horizon_months":12,
     "decision_question":"Does the second age-25-29 labour-market rate add stable value for outmigration?",
     "summaries":summaries}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in preds for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(preds)
print(json.dumps(res,ensure_ascii=False,indent=2))
