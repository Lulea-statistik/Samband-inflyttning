#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

FEATURES=Path("docs/data/short_term_monthly_candidate_family_1.csv")
TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/short_term_monthly_bas_robustness.json")
PRED=Path("docs/data/short_term_monthly_bas_robustness_predictions.csv")

HORIZONS=[3,6,9,12]
MIN_TRAIN=24
ALPHAS=[3.0,10.0,30.0]

ARMS={
 "seasonal":[],
 "bas_yoy":[
   "bas_workplace_employed_yoy_pct",
   "bas_residence_employed_yoy_pct"
 ],
 "bas_gap":[
   "bas_workplace_residence_gap_pct"
 ],
 "bas_yoy_gap":[
   "bas_workplace_employed_yoy_pct",
   "bas_residence_employed_yoy_pct",
   "bas_workplace_residence_gap_pct"
 ],
 "bas_3m":[
   "bas_workplace_employed_change_3m_pct",
   "bas_residence_employed_change_3m_pct",
   "bas_workplace_residence_gap_pct"
 ],
 "bas_6m":[
   "bas_workplace_employed_change_6m_pct",
   "bas_residence_employed_change_6m_pct",
   "bas_workplace_residence_gap_pct"
 ],
 "bas_yoy_3m":[
   "bas_workplace_employed_yoy_pct",
   "bas_residence_employed_yoy_pct",
   "bas_workplace_employed_change_3m_pct",
   "bas_residence_employed_change_3m_pct"
 ]
}

ALL_FEATURES=sorted(set(x for v in ARMS.values() for x in v))

def read(path):
    with path.open(encoding="utf-8") as f: return list(csv.DictReader(f))
def num(x):
    try:
        if x is None or x=="": return None
        v=float(x); return v if math.isfinite(v) else None
    except: return None
def mi(s): return int(s[:4])*12+int(s[-2:])
def rmse(e): return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e): return sum(abs(x) for x in e)/len(e) if e else None
def bias(e): return sum(e)/len(e) if e else None
def pct(a,b): return 100*(a/b-1) if a is not None and b not in (None,0) else None

fr={r["month"]:r for r in read(FEATURES)}
tr={r["month"]:r for r in read(TARGET)}
months=sorted(tr,key=mi); idx={mi(m):m for m in months}

def target_sum(k,h):
    mm=[idx.get(k+i) for i in range(1,h+1)]
    if any(x is None for x in mm): return None,None
    vals=[num(tr[x]["all_inmigrations"]) for x in mm]
    if any(v is None for v in vals): return None,None
    return sum(vals),mm[-1]

def seasonal_sum(k,h):
    mm=[idx.get(k+i-12) for i in range(1,h+1)]
    if any(x is None for x in mm): return None
    vals=[num(tr[x]["all_inmigrations"]) for x in mm]
    return None if any(v is None for v in vals) else sum(vals)

summaries={}
predictions=[]

for h in HORIZONS:
    base=[]
    for m in months:
        rr=fr.get(m)
        if not rr: continue
        x={c:num(rr.get(c)) for c in ALL_FEATURES}
        if any(v is None for v in x.values()): continue
        k=mi(m); actual,end=target_sum(k,h); seasonal=seasonal_sum(k,h)
        if actual is None or seasonal is None: continue
        base.append({"origin":m,"k":k,"actual":actual,"end":end,"seasonal":seasonal,"residual":actual-seasonal,"x":x})

    stats_by_alpha={}
    for alpha in ALPHAS:
        hp=[]
        for i,row in enumerate(base):
            train=[r for r in base[:i] if mi(r["end"])<=row["k"]]
            if len(train)<MIN_TRAIN: continue
            rec={"horizon_months":h,"alpha":alpha,"origin":row["origin"],"target_end":row["end"],"actual":row["actual"],
                 "seasonal":row["seasonal"],"seasonal_error":row["seasonal"]-row["actual"],"n_train":len(train)}
            for arm,features in ARMS.items():
                if arm=="seasonal": continue
                X=np.asarray([[r["x"][c] for c in features] for r in train],dtype=float)
                y=np.asarray([r["residual"] for r in train],dtype=float)
                model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
                model.fit(X,y)
                pred=row["seasonal"]+float(model.predict(np.asarray([[row["x"][c] for c in features]],dtype=float))[0])
                rec[arm]=pred; rec[arm+"_error"]=pred-row["actual"]
            hp.append(rec); predictions.append(rec)

        stats={}
        b=[r["seasonal_error"] for r in hp]
        stats["seasonal"]={"rmse":rmse(b),"mae":mae(b),"bias":bias(b)}
        for arm in [a for a in ARMS if a!="seasonal"]:
            e=[r[arm+"_error"] for r in hp]
            pre=[r[arm+"_error"] for r in hp if r["target_end"]<"2025M01"]
            post=[r[arm+"_error"] for r in hp if r["origin"]>="2025M01"]
            stats[arm]={
              "rmse":rmse(e),"mae":mae(e),"bias":bias(e),
              "delta_rmse_pct_vs_seasonal":pct(rmse(e),stats["seasonal"]["rmse"]),
              "delta_mae_pct_vs_seasonal":pct(mae(e),stats["seasonal"]["mae"]),
              "pre_2025_rmse":rmse(pre),"post_2025_rmse":rmse(post)
            }
        stats_by_alpha[str(alpha)]={
          "n_origins":len(hp),
          "ranked_by_rmse":sorted(stats,key=lambda a: stats[a]["rmse"] if stats[a]["rmse"] is not None else 1e99),
          "stats":stats
        }
    summaries[str(h)]=stats_by_alpha

result={
 "status":"short_term_monthly_bas_robustness",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "purpose":"Test whether BAS signal is robust to fixed feature representations and regularization strengths.",
 "target":"sum Lulea all_inmigrations over t+1..t+h",
 "baseline":"same future calendar months one year earlier",
 "alphas":ALPHAS,
 "arms":ARMS,
 "horizons_months":HORIZONS,
 "selection_rule":"No arm or alpha is promoted from this test alone; robustness requires improvement across multiple horizons and settings.",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in predictions for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(predictions)
print(json.dumps(result,ensure_ascii=False,indent=2))
