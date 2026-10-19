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
OUT=Path("docs/data/short_term_monthly_labour_rates_robustness.json")
PRED=Path("docs/data/short_term_monthly_labour_rates_robustness_predictions.csv")

HORIZONS=[3,6,9,12]
ALPHAS=[3.0,10.0,30.0]
MIN_TRAIN=24

ARMS={
 "seasonal":[],
 "emp_rate_20_24":["bas2_age20_24_sysselsattningsgrad_yoy_pp"],
 "emp_rate_25_29":["bas2_age25_29_sysselsattningsgrad_yoy_pp"],
 "emp_rates_both":[
   "bas2_age20_24_sysselsattningsgrad_yoy_pp",
   "bas2_age25_29_sysselsattningsgrad_yoy_pp"
 ],
 "lfp_20_24":["bas2_age20_24_arbetskraftsdeltagande_yoy_pp"],
 "lfp_25_29":["bas2_age25_29_arbetskraftsdeltagande_yoy_pp"],
 "lfp_both":[
   "bas2_age20_24_arbetskraftsdeltagande_yoy_pp",
   "bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
 ],
 "rates_20_24":[
   "bas2_age20_24_sysselsattningsgrad_yoy_pp",
   "bas2_age20_24_arbetskraftsdeltagande_yoy_pp"
 ],
 "rates_25_29":[
   "bas2_age25_29_sysselsattningsgrad_yoy_pp",
   "bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
 ],
 "rates_both_ages":[
   "bas2_age20_24_sysselsattningsgrad_yoy_pp",
   "bas2_age25_29_sysselsattningsgrad_yoy_pp",
   "bas2_age20_24_arbetskraftsdeltagande_yoy_pp",
   "bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
 ]
}

ALL=sorted(set(x for v in ARMS.values() for x in v))

def read(path):
    with path.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x is None or x=="": return None
        v=float(x); return v if math.isfinite(v) else None
    except:return None
def mi(s): return int(s[:4])*12+int(s[-2:])
def rmse(e): return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e): return sum(abs(x) for x in e)/len(e) if e else None
def bias(e): return sum(e)/len(e) if e else None
def pct(a,b): return 100*(a/b-1) if a is not None and b not in (None,0) else None

fr={r["month"]:r for r in read(FEATURES)}
tr={r["month"]:r for r in read(TARGET)}
months=sorted(tr,key=mi); idx={mi(m):m for m in months}

def tsum(k,h,off=0):
    mm=[idx.get(k+i+off) for i in range(1,h+1)]
    if any(m is None for m in mm):return None,None
    vv=[num(tr[m]["all_inmigrations"]) for m in mm]
    if any(v is None for v in vv):return None,None
    return sum(vv),mm[-1]

summaries={}
preds=[]

for h in HORIZONS:
    base=[]
    for m in months:
        rr=fr.get(m)
        if not rr:continue
        x={c:num(rr.get(c)) for c in ALL}
        if any(v is None for v in x.values()):continue
        k=mi(m)
        actual,end=tsum(k,h,0); seasonal,_=tsum(k,h,-12)
        if actual is None or seasonal is None:continue
        base.append({"origin":m,"k":k,"end":end,"actual":actual,"seasonal":seasonal,"resid":actual-seasonal,"x":x})

    by_alpha={}
    for alpha in ALPHAS:
        rows_out=[]
        for i,row in enumerate(base):
            train=[r for r in base[:i] if mi(r["end"])<=row["k"]]
            if len(train)<MIN_TRAIN:continue
            rec={"horizon_months":h,"alpha":alpha,"origin":row["origin"],"target_end":row["end"],
                 "actual":row["actual"],"seasonal":row["seasonal"],
                 "seasonal_error":row["seasonal"]-row["actual"],"n_train":len(train)}
            for arm,features in ARMS.items():
                if arm=="seasonal":continue
                X=np.asarray([[r["x"][c] for c in features] for r in train],dtype=float)
                y=np.asarray([r["resid"] for r in train],dtype=float)
                model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
                model.fit(X,y)
                p=row["seasonal"]+float(model.predict(np.asarray([[row["x"][c] for c in features]],dtype=float))[0])
                rec[arm+"_error"]=p-row["actual"]
            rows_out.append(rec);preds.append(rec)

        stats={}
        se=[r["seasonal_error"] for r in rows_out]
        stats["seasonal"]={"rmse":rmse(se),"mae":mae(se),"bias":bias(se)}
        for arm in [a for a in ARMS if a!="seasonal"]:
            e=[r[arm+"_error"] for r in rows_out]
            pre=[r[arm+"_error"] for r in rows_out if r["target_end"]<"2025M01"]
            post=[r[arm+"_error"] for r in rows_out if r["origin"]>="2025M01"]
            stats[arm]={
              "rmse":rmse(e),"mae":mae(e),"bias":bias(e),
              "delta_rmse_pct_vs_seasonal":pct(rmse(e),stats["seasonal"]["rmse"]),
              "delta_mae_pct_vs_seasonal":pct(mae(e),stats["seasonal"]["mae"]),
              "pre_2025_rmse":rmse(pre),"post_2025_rmse":rmse(post)
            }
        by_alpha[str(alpha)]={
          "n_origins":len(rows_out),
          "ranked_by_rmse":sorted(stats,key=lambda a: stats[a]["rmse"] if stats[a]["rmse"] is not None else 1e99),
          "stats":stats
        }
    summaries[str(h)]=by_alpha

result={
 "status":"short_term_monthly_labour_rates_robustness",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "purpose":"Test robustness of the promising young-adult BAS labour-rate signal.",
 "target":"sum Lulea all_inmigrations over t+1..t+h",
 "baseline":"same future calendar months one year earlier",
 "alphas":ALPHAS,
 "arms":ARMS,
 "selection_rule":"No arm is promoted unless gains persist across horizons, age decompositions and regularization settings.",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in preds for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(preds)
print(json.dumps(result,ensure_ascii=False,indent=2))
