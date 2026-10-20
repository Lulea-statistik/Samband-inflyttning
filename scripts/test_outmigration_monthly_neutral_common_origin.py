#!/usr/bin/env python3
"""Neutral monthly outmigration candidate comparison for Lulea.

Target:
  all_outmigrations from the existing stitched monthly SCB target.

Baseline:
  same future calendar months one year earlier.

Candidate families are reused only as a gross list from the inflow work:
- BAS workplace/residence employment YoY
- age 25-29 employment-rate / labour-force-participation YoY pp

No inflow monthly winner is privileged. All arms are compared on identical
forecast origins for horizons 3/6/9/12 months.

Research only; annual outmigration blend remains unchanged.
"""
import csv, json, math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F1=Path("docs/data/short_term_monthly_candidate_family_1.csv")
F2=Path("docs/data/short_term_monthly_candidate_family_2.csv")
TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/outmigration_monthly_neutral_common_origin_comparison.json")
PRED=Path("docs/data/outmigration_monthly_neutral_common_origin_predictions.csv")

HORIZONS=[3,6,9,12]
ALPHAS=[3.0,10.0,30.0]
MIN_TRAIN=24

ARMS={
 "family1_bas_yoy_lag1":{
   "source":"f1","lag":1,
   "features":["bas_workplace_employed_yoy_pct","bas_residence_employed_yoy_pct"]
 },
 "family1_bas_yoy_lag2":{
   "source":"f1","lag":2,
   "features":["bas_workplace_employed_yoy_pct","bas_residence_employed_yoy_pct"]
 },
 "rates_25_29_lag1":{
   "source":"f2","lag":1,
   "features":["bas2_age25_29_sysselsattningsgrad_yoy_pp","bas2_age25_29_arbetskraftsdeltagande_yoy_pp"]
 },
 "rates_25_29_lag2":{
   "source":"f2","lag":2,
   "features":["bas2_age25_29_sysselsattningsgrad_yoy_pp","bas2_age25_29_arbetskraftsdeltagande_yoy_pp"]
 }
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

f1={r["month"]:r for r in read(F1)}
f2={r["month"]:r for r in read(F2)}
tr={r["month"]:r for r in read(TARGET)}
months=sorted(tr,key=mi)
idx={mi(m):m for m in months}

def target_sum(k,h,shift=0):
    labs=[idx.get(k+i+shift) for i in range(1,h+1)]
    if any(x is None for x in labs):return None,None
    vals=[num(tr[x].get("all_outmigrations")) for x in labs]
    if any(v is None for v in vals):return None,None
    return sum(vals),labs[-1]

def arm_x(origin,spec):
    fm=idx.get(mi(origin)-spec["lag"])
    if fm is None:return None,None
    src=f1 if spec["source"]=="f1" else f2
    row=src.get(fm)
    if not row:return None,None
    x=[num(row.get(c)) for c in spec["features"]]
    if any(v is None for v in x):return None,None
    return x,fm

summaries={}
preds=[]

for h in HORIZONS:
    common=[]
    for origin in months:
        k=mi(origin)
        actual,end=target_sum(k,h,0)
        seasonal,_=target_sum(k,h,-12)
        if actual is None or seasonal is None:continue

        xs={}; fms={}; valid=True
        for arm,spec in ARMS.items():
            x,fm=arm_x(origin,spec)
            if x is None:
                valid=False;break
            xs[arm]=x;fms[arm]=fm
        if not valid:continue

        common.append({
          "origin":origin,"k":k,"target_end":end,
          "actual":actual,"seasonal":seasonal,
          "residual":actual-seasonal,
          "x":xs,"feature_months":fms
        })

    hs={}
    for alpha in ALPHAS:
        rows=[]
        for i,row in enumerate(common):
            train=[r for r in common[:i] if mi(r["target_end"])<=row["k"]]
            if len(train)<MIN_TRAIN:continue
            rec={
              "horizon_months":h,"alpha":alpha,"origin":row["origin"],
              "target_end":row["target_end"],"n_train":len(train),
              "actual":row["actual"],"seasonal":row["seasonal"],
              "seasonal_error":row["seasonal"]-row["actual"]
            }
            for arm,spec in ARMS.items():
                X=np.asarray([r["x"][arm] for r in train],dtype=float)
                y=np.asarray([r["residual"] for r in train],dtype=float)
                model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
                model.fit(X,y)
                pred=row["seasonal"]+float(model.predict(np.asarray([row["x"][arm]],dtype=float))[0])
                rec[arm]=pred
                rec[arm+"_error"]=pred-row["actual"]
                rec[arm+"_feature_month"]=row["feature_months"][arm]
            rows.append(rec);preds.append(rec)

        stats={}
        se=[r["seasonal_error"] for r in rows]
        srm,sma=rmse(se),mae(se)
        stats["seasonal"]={"rmse":srm,"mae":sma,"bias":bias(se)}
        for arm in ARMS:
            e=[r[arm+"_error"] for r in rows]
            stats[arm]={
              "rmse":rmse(e),"mae":mae(e),"bias":bias(e),
              "delta_rmse_pct_vs_seasonal":pct(rmse(e),srm),
              "delta_mae_pct_vs_seasonal":pct(mae(e),sma)
            }
        hs[str(alpha)]={
          "n_origins":len(rows),
          "first_origin":rows[0]["origin"] if rows else None,
          "last_origin":rows[-1]["origin"] if rows else None,
          "ranked_by_rmse":sorted(stats,key=lambda a: stats[a]["rmse"] if stats[a]["rmse"] is not None else 1e99),
          "stats":stats
        }
    summaries[str(h)]=hs

result={
 "status":"outmigration_monthly_neutral_common_origin_comparison",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "target":"all_outmigrations",
 "backward_window_months":12,
 "baseline":"same future calendar months one year earlier",
 "horizons_months":HORIZONS,
 "alphas":ALPHAS,
 "arms":ARMS,
 "common_origin_rule":"Origin retained only when all candidate arms, target, and seasonal baseline are available.",
 "training_rule":"Only historical rows whose full target window ended by current origin may enter training.",
 "selection_rule":"No candidate family is privileged by the inflow result.",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in preds for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(preds)
print(json.dumps(result,ensure_ascii=False,indent=2))
