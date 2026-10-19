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
OUT=Path("docs/data/short_term_monthly_family_2_group_benchmark.json")
PRED=Path("docs/data/short_term_monthly_family_2_group_predictions.csv")

HORIZONS=[3,6,9,12]
MIN_TRAIN=24
ALPHA=10.0

GROUPS={
 "students_young":[
  "bas2_age20_24_antal_studerande_yoy_pct",
  "bas2_age25_29_antal_studerande_yoy_pct",
  "bas2_age20_24_antal_studerande_change_3m_pct",
  "bas2_age25_29_antal_studerande_change_3m_pct"
 ],
 "unemployment":[
  "bas2_age20_24_arbetsloshet_yoy_pct",
  "bas2_age25_29_arbetsloshet_yoy_pct",
  "bas2_age20_66_antal_arbetslosa_change_3m_pct"
 ],
 "labour_rates":[
  "bas2_age20_66_sysselsattningsgrad_yoy_pct",
  "bas2_age20_66_arbetskraftsdeltagande_change_3m_pct",
  "bas2_age20_66_arbetsloshet_change_3m_pct"
 ],
 "broad_status":[
  "bas2_all_15_74_antal_studerande_yoy_pct",
  "bas2_all_15_74_antal_ovriga_yoy_pct",
  "bas2_all_15_74_antal_sysselsatta_yoy_pct",
  "bas2_all_15_74_sysselsattningsgrad_yoy_pct"
 ],
 "birth_region":[
  "bas2_foreign_born_15_74_antal_studerande_yoy_pct",
  "bas2_foreign_born_15_74_antal_sysselsatta_yoy_pct",
  "bas2_native_15_74_antal_studerande_yoy_pct",
  "bas2_native_15_74_antal_sysselsatta_yoy_pct"
 ],
 "cars":[
  "cars_new_total_yoy_pct",
  "cars_new_total_change_3m_pct",
  "cars_new_total_change_6m_pct"
 ]
}

def read(path):
    with path.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x is None or x=="":return None
        v=float(x);return v if math.isfinite(v) else None
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

preds=[]
summaries={}

for h in HORIZONS:
    hsum={}
    for group,features in GROUPS.items():
        data=[]
        for m in months:
            rr=fr.get(m)
            if not rr:continue
            x=[num(rr.get(c)) for c in features]
            if any(v is None for v in x):continue
            k=mi(m)
            actual,end=tsum(k,h,0)
            seasonal,_=tsum(k,h,-12)
            if actual is None or seasonal is None:continue
            data.append({"origin":m,"k":k,"end":end,"x":x,"actual":actual,"seasonal":seasonal,"resid":actual-seasonal})

        gp=[]
        for i,row in enumerate(data):
            train=[r for r in data[:i] if mi(r["end"])<=row["k"]]
            if len(train)<MIN_TRAIN:continue
            X=np.asarray([r["x"] for r in train],dtype=float)
            y=np.asarray([r["resid"] for r in train],dtype=float)
            model=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
            model.fit(X,y)
            corr=float(model.predict(np.asarray([row["x"]],dtype=float))[0])
            pred=row["seasonal"]+corr
            rec={"horizon_months":h,"group":group,"origin":row["origin"],"target_end":row["end"],"n_train":len(train),
                 "actual":row["actual"],"seasonal":row["seasonal"],"prediction":pred,
                 "seasonal_error":row["seasonal"]-row["actual"],"model_error":pred-row["actual"]}
            gp.append(rec);preds.append(rec)

        se=[r["seasonal_error"] for r in gp]
        me=[r["model_error"] for r in gp]
        pre=[r for r in gp if r["target_end"]<"2025M01"]
        post=[r for r in gp if r["origin"]>="2025M01"]
        hsum[group]={
          "features":features,
          "n_origins":len(gp),
          "first_origin":gp[0]["origin"] if gp else None,
          "last_origin":gp[-1]["origin"] if gp else None,
          "seasonal":{"rmse":rmse(se),"mae":mae(se),"bias":bias(se)},
          "model":{"rmse":rmse(me),"mae":mae(me),"bias":bias(me)},
          "delta_pct":{"rmse":pct(rmse(me),rmse(se)),"mae":pct(mae(me),mae(se))},
          "pre_2025_rmse":rmse([r["model_error"] for r in pre]),
          "post_2025_rmse":rmse([r["model_error"] for r in post])
        }
    summaries[str(h)]=hsum

result={
 "status":"short_term_monthly_family_2_group_benchmark",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "target":"sum of Lulea all_inmigrations over t+1..t+h",
 "baseline":"same future calendar months previous year",
 "model":"fixed Ridge correction to seasonal baseline",
 "ridge_alpha":ALPHA,
 "min_train_origins":MIN_TRAIN,
 "groups":GROUPS,
 "income_excluded_reason":"Monthly income starts 2025M01 and is too short for formal rolling backtest.",
 "horizons_months":HORIZONS,
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=["horizon_months","group","origin","target_end","n_train","actual","seasonal","prediction","seasonal_error","model_error"]
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(preds)
print(json.dumps(result,ensure_ascii=False,indent=2))
