#!/usr/bin/env python3
"""Compare backward-change windows for the simple 12-month outmigration module.

Fixed design:
- target: next 12 months all_outmigrations
- single feature: age 25-29 employment-rate change
- lag: 1 month
- Ridge alpha: 30

Windows compared on identical forecast origins:
- 12m YoY pp
- 9m pp
- 6m pp
- 3m pp
"""
import csv,json,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F=Path("docs/data/short_term_monthly_candidate_family_2.csv")
T=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/outmigration_monthly_12m_backward_window_comparison.json")
PRED=Path("docs/data/outmigration_monthly_12m_backward_window_predictions.csv")

H=12
ALPHA=30.0
LAG=1
MIN_TRAIN=24
FEATURES={
 "w12":"bas2_age25_29_sysselsattningsgrad_yoy_pp",
 "w9":"bas2_age25_29_sysselsattningsgrad_change_9m_pp",
 "w6":"bas2_age25_29_sysselsattningsgrad_change_6m_pp",
 "w3":"bas2_age25_29_sysselsattningsgrad_change_3m_pp"
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

fr={r["month"]:r for r in read(F)}
tr={r["month"]:r for r in read(T)}
months=sorted(tr,key=mi)
idx={mi(m):m for m in months}

def tsum(k,shift=0):
    labs=[idx.get(k+i+shift) for i in range(1,H+1)]
    if any(x is None for x in labs):return None,None
    vals=[num(tr[x].get("all_outmigrations")) for x in labs]
    if any(v is None for v in vals):return None,None
    return sum(vals),labs[-1]

base=[]
for origin in months:
    k=mi(origin)
    actual,end=tsum(k,0)
    seasonal,_=tsum(k,-12)
    if actual is None or seasonal is None:continue
    fm=idx.get(k-LAG)
    if fm is None or fm not in fr:continue
    xs={w:num(fr[fm].get(col)) for w,col in FEATURES.items()}
    if any(v is None for v in xs.values()):continue
    base.append({
      "origin":origin,"k":k,"target_end":end,"actual":actual,
      "seasonal":seasonal,"residual":actual-seasonal,"feature_month":fm,"x":xs
    })

rows=[]
for i,row in enumerate(base):
    train=[r for r in base[:i] if mi(r["target_end"])<=row["k"]]
    if len(train)<MIN_TRAIN:continue
    rec={
      "origin":row["origin"],"target_end":row["target_end"],"actual":row["actual"],
      "seasonal":row["seasonal"],"seasonal_error":row["seasonal"]-row["actual"],
      "feature_month":row["feature_month"],"n_train":len(train)
    }
    for w in FEATURES:
        X=np.asarray([[r["x"][w]] for r in train],float)
        y=np.asarray([r["residual"] for r in train],float)
        m=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
        m.fit(X,y)
        p=row["seasonal"]+float(m.predict(np.asarray([[row["x"][w]]],float))[0])
        rec[w]=p; rec[w+"_error"]=p-row["actual"]
    rows.append(rec)

se=[r["seasonal_error"] for r in rows]
stats={"seasonal":{"rmse":rmse(se),"mae":mae(se),"bias":bias(se)}}
for w in FEATURES:
    e=[r[w+"_error"] for r in rows]
    stats[w]={
      "rmse":rmse(e),"mae":mae(e),"bias":bias(e),
      "delta_rmse_pct_vs_seasonal":pct(rmse(e),rmse(se)),
      "delta_mae_pct_vs_seasonal":pct(mae(e),mae(se))
    }

rank=sorted(FEATURES,key=lambda w:stats[w]["rmse"])
best=rank[0] if rank else None
res={
 "status":"outmigration_monthly_12m_backward_window_comparison",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "target":"all_outmigrations",
 "horizon_months":12,
 "lag_months":1,
 "alpha":30.0,
 "n_origins":len(rows),
 "first_origin":rows[0]["origin"] if rows else None,
 "last_origin":rows[-1]["origin"] if rows else None,
 "windows_months":{"w12":12,"w9":9,"w6":6,"w3":3},
 "common_origin_rule":"All 12/9/6/3-month feature windows, target and seasonal baseline must be available.",
 "stats":stats,
 "ranked_by_rmse":rank,
 "best_window":best,
 "decision_note":"Window comparison only; no annual/monthly integration is performed here."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in rows for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    wr=csv.DictWriter(f,fieldnames=cols);wr.writeheader();wr.writerows(rows)
print(json.dumps(res,ensure_ascii=False,indent=2))
