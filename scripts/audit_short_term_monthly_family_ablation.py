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
OUT=Path("docs/data/short_term_monthly_family_ablation.json")
PRED=Path("docs/data/short_term_monthly_family_ablation_predictions.csv")
HORIZONS=[3,6,9,12]
MIN_TRAIN=24
ALPHA=10.0

FAMILIES={
 "bas":[
   "bas_workplace_employed_yoy_pct",
   "bas_residence_employed_yoy_pct",
   "bas_workplace_residence_gap_pct"
 ],
 "gdp":[
   "gdp_kalenderkorrigerad_volymforandring_fran_motsvarande_manad_foreg_ar_procent",
   "gdp_sasongrensad_volymforandring_fran_foregaende_manad_procent"
 ],
 "asylum":[
   "asylum_seekers_sweden_change_3m_pct"
 ]
}
ARMS={
 "seasonal":[],
 "bas":FAMILIES["bas"],
 "gdp":FAMILIES["gdp"],
 "asylum":FAMILIES["asylum"],
 "bas_gdp":FAMILIES["bas"]+FAMILIES["gdp"],
 "bas_asylum":FAMILIES["bas"]+FAMILIES["asylum"],
 "gdp_asylum":FAMILIES["gdp"]+FAMILIES["asylum"],
 "all":FAMILIES["bas"]+FAMILIES["gdp"]+FAMILIES["asylum"]
}
ALL_FEATURES=ARMS["all"]

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

predictions=[]
summaries={}
for h in HORIZONS:
    base_rows=[]
    # Fair common-origin dataset: require all family-1 features for every arm.
    for m in months:
        r=fr.get(m)
        if not r: continue
        xall={c:num(r.get(c)) for c in ALL_FEATURES}
        if any(v is None for v in xall.values()): continue
        k=mi(m); actual,end=target_sum(k,h); seasonal=seasonal_sum(k,h)
        if actual is None or seasonal is None: continue
        base_rows.append({
          "origin":m,"k":k,"actual":actual,"end":end,"seasonal":seasonal,
          "residual":actual-seasonal,"x":xall
        })

    hp=[]
    for i,row in enumerate(base_rows):
        train=[r for r in base_rows[:i] if mi(r["end"])<=row["k"]]
        if len(train)<MIN_TRAIN: continue
        rec={"horizon_months":h,"origin":row["origin"],"target_end":row["end"],
             "n_train":len(train),"actual":row["actual"],"seasonal":row["seasonal"],
             "seasonal_error":row["seasonal"]-row["actual"]}
        for arm,features in ARMS.items():
            if arm=="seasonal": continue
            X=np.asarray([[r["x"][c] for c in features] for r in train],dtype=float)
            y=np.asarray([r["residual"] for r in train],dtype=float)
            model=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
            model.fit(X,y)
            corr=float(model.predict(np.asarray([[row["x"][c] for c in features]],dtype=float))[0])
            pred=row["seasonal"]+corr
            rec[arm]=pred; rec[arm+"_error"]=pred-row["actual"]
        hp.append(rec); predictions.append(rec)

    stats={}
    base_err=[r["seasonal_error"] for r in hp]
    stats["seasonal"]={"rmse":rmse(base_err),"mae":mae(base_err),"bias":bias(base_err)}
    for arm in [a for a in ARMS if a!="seasonal"]:
        errs=[r[arm+"_error"] for r in hp]
        pre=[r[arm+"_error"] for r in hp if r["target_end"]<"2025M01"]
        post=[r[arm+"_error"] for r in hp if r["origin"]>="2025M01"]
        stats[arm]={
          "rmse":rmse(errs),"mae":mae(errs),"bias":bias(errs),
          "delta_rmse_pct_vs_seasonal":pct(rmse(errs),stats["seasonal"]["rmse"]),
          "delta_mae_pct_vs_seasonal":pct(mae(errs),stats["seasonal"]["mae"]),
          "pre_2025_rmse":rmse(pre),"post_2025_rmse":rmse(post)
        }
    ranked=sorted(stats,key=lambda a: stats[a]["rmse"] if stats[a]["rmse"] is not None else 1e99)
    summaries[str(h)]={
      "n_origins":len(hp),
      "first_origin":hp[0]["origin"] if hp else None,
      "last_origin":hp[-1]["origin"] if hp else None,
      "ranked_by_rmse":ranked,
      "stats":stats
    }

result={
 "status":"short_term_monthly_family_ablation",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "purpose":"Identify which candidate family carries incremental signal on identical rolling origins.",
 "fairness":"All arms evaluated on the same origins requiring complete BAS, GDP and asylum features.",
 "target":"sum Lulea all_inmigrations over t+1..t+h",
 "baseline":"same future calendar months one year earlier",
 "model":"Ridge correction to seasonal baseline",
 "ridge_alpha":ALPHA,
 "min_train_origins":MIN_TRAIN,
 "families":FAMILIES,
 "arms":ARMS,
 "horizons_months":HORIZONS,
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=sorted({k for r in predictions for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(predictions)
print(json.dumps(result,ensure_ascii=False,indent=2))
