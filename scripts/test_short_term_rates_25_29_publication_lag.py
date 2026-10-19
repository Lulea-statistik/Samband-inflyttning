#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

FEATURES=Path("docs/data/short_term_monthly_candidate_family_2.csv")
TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/short_term_monthly_rates_25_29_publication_lag.json")
PRED=Path("docs/data/short_term_monthly_rates_25_29_publication_lag_predictions.csv")

FEATURES_USED=[
 "bas2_age25_29_sysselsattningsgrad_yoy_pp",
 "bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
]
HORIZONS=[3,6,9,12]
LAGS=[0,1,2]
ALPHAS=[3.0,10.0,30.0]
MIN_TRAIN=24

def read(path):
    with path.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x in (None,""): return None
        v=float(x); return v if math.isfinite(v) else None
    except:return None
def mi(s): return int(s[:4])*12+int(s[-2:])
def rmse(e): return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e): return sum(abs(x) for x in e)/len(e) if e else None
def bias(e): return sum(e)/len(e) if e else None
def pct(a,b): return 100*(a/b-1) if a is not None and b not in (None,0) else None

fr={r["month"]:r for r in read(FEATURES)}
tr={r["month"]:r for r in read(TARGET)}
months=sorted(tr,key=mi)
idx={mi(m):m for m in months}

def tsum(k,h,off=0):
    mm=[idx.get(k+i+off) for i in range(1,h+1)]
    if any(m is None for m in mm):return None,None
    vv=[num(tr[m]["all_inmigrations"]) for m in mm]
    if any(v is None for v in vv):return None,None
    return sum(vv),mm[-1]

summaries={}
preds=[]

for h in HORIZONS:
    hs={}
    for lag in LAGS:
        lag_data=[]
        for origin in months:
            ok=mi(origin)
            fm=idx.get(ok-lag)
            rr=fr.get(fm) if fm else None
            if not rr: continue
            x=[num(rr.get(c)) for c in FEATURES_USED]
            if any(v is None for v in x): continue
            actual,end=tsum(ok,h,0)
            seasonal,_=tsum(ok,h,-12)
            if actual is None or seasonal is None: continue
            lag_data.append({
              "origin":origin,"feature_month":fm,"k":ok,"end":end,
              "x":x,"actual":actual,"seasonal":seasonal,"resid":actual-seasonal
            })

        by_alpha={}
        for alpha in ALPHAS:
            rows=[]
            for i,row in enumerate(lag_data):
                # Training rows must have completed targets by forecast origin.
                train=[r for r in lag_data[:i] if mi(r["end"])<=row["k"]]
                if len(train)<MIN_TRAIN: continue
                X=np.asarray([r["x"] for r in train],dtype=float)
                y=np.asarray([r["resid"] for r in train],dtype=float)
                model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
                model.fit(X,y)
                pred=row["seasonal"]+float(model.predict(np.asarray([row["x"]],dtype=float))[0])
                rec={
                  "horizon_months":h,"feature_lag_months":lag,"alpha":alpha,
                  "origin":row["origin"],"feature_month":row["feature_month"],
                  "target_end":row["end"],"n_train":len(train),
                  "actual":row["actual"],"seasonal":row["seasonal"],"prediction":pred,
                  "seasonal_error":row["seasonal"]-row["actual"],
                  "model_error":pred-row["actual"]
                }
                rows.append(rec); preds.append(rec)

            se=[r["seasonal_error"] for r in rows]
            me=[r["model_error"] for r in rows]
            pre=[r["model_error"] for r in rows if r["target_end"]<"2025M01"]
            post=[r["model_error"] for r in rows if r["origin"]>="2025M01"]
            sr,sm=rmse(se),mae(se)
            mr,mm=rmse(me),mae(me)
            by_alpha[str(alpha)]={
              "n_origins":len(rows),
              "first_origin":rows[0]["origin"] if rows else None,
              "last_origin":rows[-1]["origin"] if rows else None,
              "seasonal":{"rmse":sr,"mae":sm,"bias":bias(se)},
              "model":{"rmse":mr,"mae":mm,"bias":bias(me)},
              "delta_rmse_pct_vs_seasonal":pct(mr,sr),
              "delta_mae_pct_vs_seasonal":pct(mm,sm),
              "pre_2025_rmse":rmse(pre),
              "post_2025_rmse":rmse(post)
            }
        hs[str(lag)]=by_alpha
    summaries[str(h)]=hs

result={
 "status":"short_term_monthly_rates_25_29_publication_lag",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "candidate":"rates_25_29",
 "features":FEATURES_USED,
 "feature_lags_months":LAGS,
 "alphas":ALPHAS,
 "horizons_months":HORIZONS,
 "interpretation":{
   "lag_0":"hindsight upper bound: current-month BAS assumed available",
   "lag_1":"pseudo-realtime: use previous month BAS",
   "lag_2":"conservative pseudo-realtime: use BAS two months old"
 },
 "selection_rule":"Candidate remains provisional unless gains persist at realistic lag 1-2 months across the main 9-12 month horizons.",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in preds for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(preds)
print(json.dumps(result,ensure_ascii=False,indent=2))
