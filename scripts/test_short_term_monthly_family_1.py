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
OUT=Path("docs/data/short_term_monthly_family_1_rolling_benchmark.json")
PRED=Path("docs/data/short_term_monthly_family_1_rolling_predictions.csv")

HORIZONS=[3,6,9,12]
MIN_TRAIN=24
RIDGE_ALPHA=10.0

# Fixed before test: no feature selection/tuning.
CANDIDATE_FEATURES=[
 "bas_workplace_employed_yoy_pct",
 "bas_residence_employed_yoy_pct",
 "bas_workplace_residence_gap_pct",
 "gdp_kalenderkorrigerad_volymforandring_fran_motsvarande_manad_foreg_ar_procent",
 "gdp_sasongrensad_volymforandring_fran_foregaende_manad_procent",
 "asylum_seekers_sweden_change_3m_pct"
]

def read_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

def fnum(x):
    try:
        if x is None or x=="": return None
        v=float(x)
        return v if math.isfinite(v) else None
    except: return None

def month_index(s):
    return int(s[:4])*12+int(s[-2:])

def rmse(errs):
    return math.sqrt(sum(e*e for e in errs)/len(errs)) if errs else None

def mae(errs):
    return sum(abs(e) for e in errs)/len(errs) if errs else None

def bias(errs):
    return sum(errs)/len(errs) if errs else None

def pct(a,b):
    return 100*(a/b-1) if a is not None and b not in (None,0) else None

feature_rows={r["month"]:r for r in read_csv(FEATURES)}
target_rows={r["month"]:r for r in read_csv(TARGET)}
months=sorted(target_rows,key=month_index)
byidx={month_index(m):m for m in months}

# Build origin rows. Features must be known at origin month. Target is t+1..t+h.
def make_rows(h):
    rows=[]
    for m in months:
        k=month_index(m)
        fr=feature_rows.get(m)
        if not fr: continue
        x=[fnum(fr.get(c)) for c in CANDIDATE_FEATURES]
        if any(v is None for v in x):
            continue
        fut=[byidx.get(k+i) for i in range(1,h+1)]
        prev=[byidx.get(k+i-12) for i in range(1,h+1)]
        if any(z is None for z in fut+prev): continue
        actual_vals=[fnum(target_rows[z].get("all_inmigrations")) for z in fut]
        seasonal_vals=[fnum(target_rows[z].get("all_inmigrations")) for z in prev]
        if any(v is None for v in actual_vals+seasonal_vals): continue
        actual=sum(actual_vals)
        seasonal=sum(seasonal_vals)
        rows.append({
          "origin":m,"k":k,"x":x,"actual":actual,"seasonal":seasonal,
          "residual_target":actual-seasonal,
          "target_end":fut[-1],
          "crosses_2025_break": int(m<"2025M01" and fut[-1]>="2025M01")
        })
    return rows

all_predictions=[]
summaries={}
for h in HORIZONS:
    rows=make_rows(h)
    preds=[]
    for i,row in enumerate(rows):
        train=rows[:i]
        # Strict rolling origin; at least MIN_TRAIN earlier origins.
        # Avoid label leakage from overlapping future windows: training target must end <= current origin.
        train=[r for r in train if month_index(r["target_end"]) <= row["k"]]
        if len(train)<MIN_TRAIN: continue
        X=np.asarray([r["x"] for r in train],dtype=float)
        y=np.asarray([r["residual_target"] for r in train],dtype=float)
        model=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA))
        model.fit(X,y)
        correction=float(model.predict(np.asarray([row["x"]],dtype=float))[0])
        monthly_pred=row["seasonal"]+correction
        rec={
          "horizon_months":h,
          "origin":row["origin"],
          "target_end":row["target_end"],
          "n_train":len(train),
          "actual":row["actual"],
          "seasonal_naive":row["seasonal"],
          "monthly_model":monthly_pred,
          "monthly_correction":correction,
          "seasonal_error":row["seasonal"]-row["actual"],
          "monthly_error":monthly_pred-row["actual"],
          "crosses_2025_break":row["crosses_2025_break"]
        }
        preds.append(rec)
        all_predictions.append(rec)

    se=[r["seasonal_error"] for r in preds]
    me=[r["monthly_error"] for r in preds]
    pre=[r for r in preds if r["target_end"]<"2025M01"]
    post=[r for r in preds if r["origin"]>="2025M01"]
    summaries[str(h)]={
      "n_origins":len(preds),
      "first_origin":preds[0]["origin"] if preds else None,
      "last_origin":preds[-1]["origin"] if preds else None,
      "seasonal_naive":{"rmse":rmse(se),"mae":mae(se),"bias":bias(se)},
      "monthly_model":{"rmse":rmse(me),"mae":mae(me),"bias":bias(me)},
      "delta_pct":{
        "rmse":pct(rmse(me),rmse(se)),
        "mae":pct(mae(me),mae(se))
      },
      "pre_2025":{
        "n":len(pre),
        "seasonal_rmse":rmse([r["seasonal_error"] for r in pre]),
        "monthly_rmse":rmse([r["monthly_error"] for r in pre])
      },
      "post_2025":{
        "n":len(post),
        "seasonal_rmse":rmse([r["seasonal_error"] for r in post]),
        "monthly_rmse":rmse([r["monthly_error"] for r in post])
      }
    }

OUT.parent.mkdir(parents=True,exist_ok=True)
result={
 "status":"short_term_monthly_family_1_rolling_benchmark",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "target":"sum of Lulea all_inmigrations over t+1..t+h",
 "baseline":"same forecast-calendar months one year earlier",
 "model":"fixed Ridge correction to seasonal-naive forecast",
 "ridge_alpha":RIDGE_ALPHA,
 "min_train_origins":MIN_TRAIN,
 "features":CANDIDATE_FEATURES,
 "horizons_months":HORIZONS,
 "leakage_control":"training row target_end must be <= current forecast origin",
 "source_break_2025":"reported separately; no parameter tuning on break",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

cols=["horizon_months","origin","target_end","n_train","actual","seasonal_naive","monthly_model","monthly_correction","seasonal_error","monthly_error","crosses_2025_break"]
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(all_predictions)
print(json.dumps(result,ensure_ascii=False,indent=2))
